"""VoxReel CLI Interface.

Implements Appendix B command reference from VOX_engine_Plan.md:
- voxreel ingest <file> [--lang en] [--speakers N] [--no-separation]
- voxreel process <file> --registry ./vault --out srt,json
- voxreel enroll "<Actor Name>" --from clip1.wav clip2.wav [--lang en]
- voxreel label <session_id> --map SPK_B:"Marcus Chen" --promote
- voxreel registry list | search <q> | merge <idA> <idB> | delete <id>
- voxreel export <session_id> --format srt,vtt,eaf,json,txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from modules.voxreel.config import VoxReelConfig
from modules.voxreel.db import VoxReelDB
from modules.voxreel.engine import VoxReelEngine
from modules.voxreel.registry import ActorVoiceRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voxreel",
        description="VoxReel — Speaker Diarization & Actor Voice Registry Engine",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Ingest command
    ingest_p = subparsers.add_parser("ingest", help="Ingest and condition media file to 16k mono WAV")
    ingest_p.add_argument("file", help="Path to input media file")
    ingest_p.add_argument("--out", "-o", default=None, help="Output WAV path")
    ingest_p.add_argument("--lang", default="en", help="Language code")
    ingest_p.add_argument("--speakers", type=int, default=None, help="Force speaker count")
    ingest_p.add_argument("--no-separation", action="store_true", help="Disable vocal separation pre-pass")

    # Process command (End-to-End)
    process_p = subparsers.add_parser("process", help="Process media file end-to-end through 5-stage pipeline")
    process_p.add_argument("file", help="Path to input media file")
    process_p.add_argument("--registry", default="", help="Path to actor registry vault directory")
    process_p.add_argument("--out", default="json,srt,vtt,txt", help="Comma-separated output formats")
    process_p.add_argument("--lang", default="en", help="Language code")
    process_p.add_argument("--speakers", type=int, default=None, help="Override speaker count")
    process_p.add_argument("--no-resume", action="store_true", help="Force recomputation of all stages")

    # Enroll command
    enroll_p = subparsers.add_parser("enroll", help="Enroll actor voice profile from audio clips")
    enroll_p.add_argument("name", help="Actor display name")
    enroll_p.add_argument("--from-clips", "--from", dest="clips", nargs="+", required=True, help="Audio clip paths")
    enroll_p.add_argument("--lang", default="en", help="Language code")
    enroll_p.add_argument("--vault", default="", help="Registry vault path")

    # Label command
    label_p = subparsers.add_parser("label", help="Map cluster to actor and optionally promote to profile")
    label_p.add_argument("session_id", help="Session ID")
    label_p.add_argument("--map", required=True, help="Cluster to Actor mapping (e.g. SPK_B:'Marcus Chen')")
    label_p.add_argument("--promote", action="store_true", help="Promote cluster embeddings into actor voice profile")
    label_p.add_argument("--vault", default="", help="Registry vault path")

    # Registry management commands
    reg_p = subparsers.add_parser("registry", help="Manage Actor Voice Registry")
    reg_sub = reg_p.add_subparsers(dest="reg_action", help="Registry actions")

    reg_sub.add_parser("list", help="List all registered actors")

    search_p = reg_sub.add_parser("search", help="Search actors by name or alias")
    search_p.add_argument("query", help="Search query")

    merge_p = reg_sub.add_parser("merge", help="Merge source actor into target actor")
    merge_p.add_argument("target_id", help="Target actor ID to keep")
    merge_p.add_argument("source_id", help="Source actor ID to merge and remove")

    del_p = reg_sub.add_parser("delete", help="Delete actor and erase voice vectors (GDPR)")
    del_p.add_argument("actor_id", help="Actor ID to delete")

    # Export command
    export_p = subparsers.add_parser("export", help="Export existing session to requested formats")
    export_p.add_argument("session_id", help="Session ID to export")
    export_p.add_argument("--format", default="srt,vtt,json,eaf,txt", help="Comma-separated format list")
    export_p.add_argument("--out-dir", default=None, help="Output destination folder")
    export_p.add_argument("--vault", default="", help="Registry vault path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "ingest":
        from modules.voxreel.audio import AudioConditioner
        cond = AudioConditioner()
        in_file = Path(args.file)
        out_file = Path(args.out) if args.out else in_file.with_name(f"{in_file.stem}_16k_mono.wav")
        cond.condition_audio(
            input_path=in_file,
            output_path=out_file,
            force_center=True,
            apply_loudnorm=True,
            source_separation=not args.no_separation,
        )
        print(f"Conditioned audio written to: {out_file}")
        return 0

    elif args.command == "process":
        config = VoxReelConfig()
        if args.registry:
            config.vault_dir = args.registry
        db = VoxReelDB(config.vault_dir if config.vault_dir else None)
        engine = VoxReelEngine(config=config, db=db)
        formats = tuple(f.strip().lower() for f in args.out.split(",") if f.strip())

        def _prog(stage: str, pct: float, msg: str) -> None:
            print(f"[{int(pct*100):3d}%] {stage}: {msg}")

        result = engine.process(
            media_path=args.file,
            language=args.lang,
            num_speakers=args.speakers,
            resume=not args.no_resume,
            export_formats=formats,
            progress_cb=_prog,
        )
        print(f"\n[DONE] Session ID: {result.session_id}")
        for fmt, path in result.exported_files.items():
            print(f"  - {fmt.upper()}: {path}")
        return 0

    elif args.command == "enroll":
        db = VoxReelDB(args.vault if args.vault else None)
        registry = ActorVoiceRegistry(db=db)

        actor = registry.db.get_actor_by_name(args.name)
        if not actor:
            actor = registry.create_actor(display_name=args.name, consent_flag=True)
            print(f"Created new actor: {actor.display_name} (ID: {actor.id})")

        total_enrolled = 0
        for clip in args.clips:
            success, msg, count = registry.enroll_clip(
                actor_id=actor.id,
                audio_path=clip,
                language=args.lang,
            )
            print(f"  {clip}: {msg}")
            if success:
                total_enrolled += count

        print(f"\nEnrolled {total_enrolled} reference embedding(s) into {actor.display_name}'s profile.")
        return 0

    elif args.command == "label":
        db = VoxReelDB(args.vault if args.vault else None)
        registry = ActorVoiceRegistry(db=db)

        # Parse map string: SPK_B:"Marcus Chen" or SPK_B:Marcus Chen
        parts = args.map.split(":", 1)
        if len(parts) != 2:
            print("Error: --map must be in format 'CLUSTER:Actor Name', e.g. SPK_B:'Marcus Chen'")
            return 1

        cluster = parts[0].strip()
        actor_name = parts[1].strip().strip('"').strip("'")

        if args.promote:
            actor = registry.promote_cluster_to_actor(
                session_id=args.session_id,
                cluster_label=cluster,
                actor_name=actor_name,
            )
            print(f"Promoted cluster {cluster} to registered actor: {actor.display_name} (ID: {actor.id})")
        else:
            actor = registry.db.get_actor_by_name(actor_name)
            if not actor:
                actor = registry.create_actor(display_name=actor_name)
            registry.apply_corrections(
                session_id=args.session_id,
                corrections=[{"action": "reassign_speaker", "actor_id": actor.id, "cluster": cluster}],
            )
            print(f"Reassigned cluster {cluster} to {actor.display_name} in session {args.session_id}.")
        return 0

    elif args.command == "registry":
        db = VoxReelDB()
        registry = ActorVoiceRegistry(db=db)

        if args.reg_action == "list":
            actors = registry.list_actors()
            print(f"\n=== Registered Actors ({len(actors)}) ===")
            for a in actors:
                aliases_str = f" (aliases: {', '.join(a.aliases)})" if a.aliases else ""
                print(f"  [{a.id[:8]}] {a.display_name}{aliases_str}")
            return 0

        elif args.reg_action == "search":
            results = registry.search_actors(args.query)
            print(f"\nSearch results for '{args.query}' ({len(results)} matches):")
            for a in results:
                aliases_str = f" (aliases: {', '.join(a.aliases)})" if a.aliases else ""
                print(f"  [{a.id[:8]}] {a.display_name}{aliases_str}")
            return 0

        elif args.reg_action == "merge":
            merged = registry.merge_actors(target_id=args.target_id, source_id=args.source_id)
            if merged:
                print(f"Successfully merged into {merged.display_name} (ID: {merged.id})")
            else:
                print("Merge failed. Verify both actor IDs exist.")
            return 0

        elif args.reg_action == "delete":
            ok = registry.delete_actor(actor_id=args.actor_id)
            if ok:
                print(f"Actor {args.actor_id} and all biometric voice profiles deleted (GDPR compliant).")
            else:
                print(f"Actor {args.actor_id} not found.")
            return 0

    elif args.command == "export":
        from modules.voxreel.exporters import VoxReelExporter
        db = VoxReelDB(args.vault if args.vault else None)
        sess = db.get_session(args.session_id)
        if not sess:
            print(f"Session '{args.session_id}' not found.")
            return 1

        segments = db.get_segments(args.session_id)
        speakers = db.get_cluster_matches(args.session_id)

        master_data = {
            "session_id": args.session_id,
            "pipeline": {"voxreel": "1.0.0", "embedding_model": sess.embedding_model},
            "media": {"name": f"session_{args.session_id}.wav", "duration_sec": 0.0},
            "language": sess.language,
            "speakers": speakers,
            "segments": segments,
        }

        out_dir = Path(args.out_dir) if args.out_dir else Path.cwd() / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        export_formats = [f.strip().lower() for f in args.format.split(",") if f.strip()]

        for fmt in export_formats:
            target = out_dir / f"{args.session_id[:8]}.{fmt}"
            if fmt == "json":
                VoxReelExporter.export_json(master_data, target)
            elif fmt == "srt":
                VoxReelExporter.export_srt(master_data, target)
            elif fmt == "vtt":
                VoxReelExporter.export_vtt(master_data, target)
            elif fmt == "txt":
                VoxReelExporter.export_txt(master_data, target)
            elif fmt in ("eaf", "elan"):
                VoxReelExporter.export_elan(master_data, target.with_suffix(".eaf"))
            print(f"Exported: {target}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
