"""
VERISYNTH — Main Entry Point
Wires all subsystems together and runs the co-simulation loop.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import structlog
import yaml

from simulation.carla.manager import CarlaConfig, CarlaManager
from simulation.sumo.manager import SumoManagerConfig, SumoManager
from simulation.synchronization.cosim_sync import CosimConfig, CosimSync
from simulation.v2x.communication_engine import CommunicationEngine
from simulation.logging.packet_logger import PacketLogger
from simulation.can.can_bus import CANBus
from simulation.security.key_manager import KeyManager
from simulation.attacks.attack_scheduler import AttackScheduler
from simulation.ids.ids_manager import IDSManager
from simulation.security.pseudonym_manager import PseudonymManager
from simulation.logging.state_logger import StateLogger
from simulation.logging.event_logger import EventLogger, EventType
from simulation.carla.scene_controller import SceneController

# ── V-SOC Server ──────────────────────────────────────────────────────────────
import threading
import uvicorn
from server.api import app, sim_state
from server.adapters import adapter
from simulation.ids.trust_orchestrator import TrustOrchestrator
from simulation.v2x.rsu_manager import RSUManager

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(level: str, log_file: str, structured: bool) -> None:
    """Configure structlog + stdlib logging."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Ensure log directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    file_handler = logging.FileHandler(log_file, mode="w")
    handlers.append(file_handler)

    logging.basicConfig(
        level    = numeric_level,
        handlers = handlers,
        format   = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt  = "%H:%M:%S",
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class  = structlog.stdlib.BoundLogger,
        logger_factory = structlog.stdlib.LoggerFactory(),
    )


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_simulation_config(sim_yaml: str) -> dict:
    with open(sim_yaml) as f:
        return yaml.safe_load(f)["simulation"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # ── Paths ─────────────────────────────────────────────────────────
    SIM_YAML   = "configs/simulation.yaml"
    CARLA_YAML = "configs/carla.yaml"
    SUMO_YAML  = "configs/sumo.yaml"

    # ── Load master config for logging setup ──────────────────────────
    sim_cfg = load_simulation_config(SIM_YAML)

    setup_logging(
        level      = sim_cfg["logging"]["level"],
        log_file   = sim_cfg["logging"]["log_filename"],
        structured = sim_cfg["logging"]["structured"],
    )

    log = logging.getLogger("verisynth.main")
    log.info("=" * 60)
    log.info("VERISYNTH starting | name=%s seed=%d dt=%.4fs",
             sim_cfg["name"],
             sim_cfg["seed"],
             sim_cfg["fixed_delta_seconds"])
    log.info("=" * 60)

    # ── Build subsystem configs ───────────────────────────────────────
    carla_cfg  = CarlaConfig.from_yaml(CARLA_YAML, SIM_YAML)
    sumo_cfg   = SumoManagerConfig.from_yaml(SUMO_YAML, SIM_YAML)
    cosim_cfg  = CosimConfig.from_yaml(SIM_YAML)

    # ── Invariant check: timestep consistency ─────────────────────────
    assert carla_cfg.fixed_delta_seconds == cosim_cfg.fixed_delta_seconds, (
        f"Timestep mismatch: CARLA={carla_cfg.fixed_delta_seconds} "
        f"CosimSync={cosim_cfg.fixed_delta_seconds}"
    )
    assert sumo_cfg.launch.step_length == cosim_cfg.fixed_delta_seconds, (
        f"Timestep mismatch: SUMO={sumo_cfg.launch.step_length} "
        f"CosimSync={cosim_cfg.fixed_delta_seconds}"
    )
    log.info(
        "Timestep invariant OK | dt=%.4fs across CARLA + SUMO + CosimSync",
        cosim_cfg.fixed_delta_seconds
    )

    # ── Construct managers ────────────────────────────────────────────
    carla_manager = CarlaManager(carla_cfg)
    sumo_manager  = SumoManager(sumo_cfg)
    cosim         = CosimSync(carla_manager, sumo_manager, cosim_cfg)

    # V2X engine — built from configs, wired after SUMO starts
    import yaml as _yaml
    with open("configs/v2x.yaml") as _f:
        _v2x_enabled = _yaml.safe_load(_f)["v2x"]["enabled"]

    comm_engine = None
    if _v2x_enabled:
        comm_engine = CommunicationEngine.from_config(
            "configs/v2x.yaml", "configs/simulation.yaml"
        )
        with open("configs/v2x.yaml") as _pf:
            _v2x_cfg_full = _yaml.safe_load(_pf)["v2x"]
        packet_logger = PacketLogger.from_config(
            v2x_cfg = _v2x_cfg_full,
            sim_cfg = sim_cfg,
            run_id  = sim_cfg.get("name", ""),
        )

    # Build CAN bus + security layer
    with open("configs/v2x.yaml") as _cf:
        _sec_cfg = _yaml.safe_load(_cf)["v2x"]["security"]
    can_bus = CANBus.from_config(_sec_cfg, seed=sim_cfg["seed"])


    ids_manager = IDSManager.from_config(
        "configs/ids.yaml",
        "configs/simulation.yaml",
    )

    attack_scheduler = AttackScheduler.from_config(
        "configs/attacks.yaml",
        "configs/simulation.yaml",
    )

    key_manager = KeyManager.from_config(
        "configs/security.yaml",
        "configs/simulation.yaml",
        can_bus._auth,
    )
    pseudonym_manager = PseudonymManager.from_config(
        _yaml.safe_load(open("configs/security.yaml")),
        seed=sim_cfg["seed"],
    )

    state_logger = StateLogger.from_config(
        sim_cfg = sim_cfg,
        run_id  = sim_cfg.get("name", ""),
    )
    event_logger = EventLogger.from_config(
        sim_cfg = sim_cfg,
        run_id  = sim_cfg.get("name", ""),
    )

    # ── Run ───────────────────────────────────────────────────────────
    exit_code = 0
   # packet_logger = None  # ensure defined before try block

    try:
        log.info("Starting SUMO...")
        sumo_manager.start()
        log.info("SUMO ready | %s", sumo_manager)

        log.info("Connecting to CARLA...")
        carla_manager.connect()
        log.info("CARLA ready | %s", carla_manager)

        scene_controller = SceneController(carla_manager)
        cosim.set_scene_controller(scene_controller)
        log.info("SceneController ready | %s", scene_controller.summary())

        log.info("Initialising CosimSync (coordinate transformer)...")
        cosim.initialise()

        # V2X initialisation — requires SUMO network loaded
        if comm_engine is not None:
            import sumolib as _sumolib
            import yaml as _yaml
            with open("configs/sumo.yaml") as _f:
                _net_file = _yaml.safe_load(_f)["sumo"]["network"]["net_file"]
            _net = _sumolib.net.readNet(_net_file, withInternal=False)
            rsu_manager = RSUManager.from_config(
                yaml.safe_load(open("configs/v2x.yaml"))["v2x"],
                _net,
                carla_manager.transformer,
                fixed_dt = sim_cfg["fixed_delta_seconds"],
                seed     = sim_cfg["seed"],
            )
            rsu_manager.initialise()
            comm_engine.initialise(rsu_manager)
            cosim.set_comm_engine(comm_engine)
            log.info("V2X engine ready | %s", comm_engine)

        if packet_logger is not None:
            packet_logger.open()
            cosim.set_packet_logger(packet_logger)
            log.info("PacketLogger ready | %s", packet_logger)

        cosim.set_can_bus(can_bus)
        log.info("CANBus ready | %s", can_bus)

        cosim.set_ids_manager(ids_manager)
        log.info("IDSManager ready | %s", ids_manager)

        trust_orchestrator = TrustOrchestrator.from_config(
            ids_cfg       = yaml.safe_load(open("configs/ids.yaml")),
            trust_manager = ids_manager._trust,
            alert_manager = ids_manager.alert_manager,
        )
        cosim.set_trust_orchestrator(trust_orchestrator)
        log.info("TrustOrchestrator ready | %s", trust_orchestrator.summary())

        cosim.set_attack_scheduler(attack_scheduler)
        log.info("AttackScheduler ready | %s", attack_scheduler)

        cosim.set_key_manager(key_manager)
        log.info("KeyManager ready | %s", key_manager)

        state_logger.open()
        cosim.set_state_logger(state_logger)
        log.info("StateLogger ready | %s", state_logger)

        event_logger.open()
        cosim.set_event_logger(event_logger)
        event_logger.log_sim_start(
            sim_step = 0,
            sim_time = 0.0,
            name     = sim_cfg["name"],
            seed     = sim_cfg["seed"],
        )
        log.info("EventLogger ready | %s", event_logger)
        adapter.publish_sim_start(
            sim_cfg = sim_cfg,
            town    = scene_controller.current_town,
            weather = scene_controller.current_weather,
        )

        # ── Wire V-SOC server references ─────────────────────────────────
        sim_state.attack_scheduler   = attack_scheduler
        sim_state.scene_controller   = scene_controller
        sim_state.ids_manager        = ids_manager
        sim_state.trust_orchestrator = trust_orchestrator

        adapter.register_ids_manager(ids_manager)
        adapter.register_trust_orchestrator(trust_orchestrator)
        adapter.register_attack_scheduler(attack_scheduler)
        adapter.register_scene_controller(scene_controller)

        # ── Start FastAPI in a daemon thread ──────────────────────────────────
        def _start_api():
            uvicorn.run(
                app,
                host      = "0.0.0.0",
                port      = 8001,
                log_level = "warning",
            )

        api_thread = threading.Thread(target=_start_api, daemon=True, name="vsoc-api")
        api_thread.start()
        log.info("V-SOC API server started | http://localhost:8000")

        sim_state.mark_running()
        log.info("Starting simulation loop...")
        t_start = time.monotonic()

        stats = cosim.run()

        elapsed = time.monotonic() - t_start
        log.info("=" * 60)
        log.info("Simulation complete")
        log.info("  Steps:          %d", stats.total_steps)
        log.info("  Spawned:        %d", stats.total_spawned)
        log.info("  Despawned:      %d", stats.total_despawned)
        log.info("  Desyncs:        %d", stats.total_desyncs)
        log.info("  Peak vehicles:  %d", stats.peak_vehicles)
        log.info("  Max pos error:  %.4f m", stats.max_position_error)
        log.info("  Wall time:      %.1f s", elapsed)
        log.info("=" * 60)

    except KeyboardInterrupt:
        log.info("Interrupted by user")

    except Exception as exc:
        log.error("Fatal error: %s", exc, exc_info=True)
        exit_code = 1

    finally:
        sim_state.mark_stopped()
        adapter.publish_sim_stop(
            stats           = cosim.stats if hasattr(cosim, 'stats') else None,
            total_alerts    = ids_manager._total_alerts,
            total_injected  = attack_scheduler.stats.total_injected,
        )
        log.info("Shutting down subsystems...")
        if packet_logger is not None:
            packet_logger.close()
            log.info(packet_logger.summary())
        log.info(ids_manager.summary())
        log.info(trust_orchestrator.summary())
        log.info(scene_controller.summary())
        log.info(attack_scheduler.summary())
        log.info(key_manager.summary())
        state_logger.close()
        log.info(state_logger.summary())
        event_logger.log_sim_end(
            sim_step      = 0,
            sim_time      = 0.0,
            total_steps   = 6000,
            total_spawned = 0,
            total_desyncs = 0,
        )
        event_logger.close()
        log.info(event_logger.summary())
        try:
            carla_manager.shutdown()
        except Exception as exc:
            log.warning("CARLA shutdown error: %s", exc)
        try:
            sumo_manager.shutdown()
        except Exception as exc:
            log.warning("SUMO shutdown error: %s", exc)
        log.info("Shutdown complete")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
