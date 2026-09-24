"""VoxReel Transcript Exporters.

Implements FR-6 from VOX_engine_Plan.md:
- Master JSON format (Appendix C)
- SubRip Subtitles (.srt)
- WebVTT Subtitles (.vtt)
- ELAN Annotation Format (.eaf XML)
- Plain text transcript (.txt)
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _format_time_srt(seconds: float) -> str:
    """Format seconds into SRT timestamp: HH:MM:SS,mmm."""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _format_time_vtt(seconds: float) -> str:
    """Format seconds into WebVTT timestamp: HH:MM:SS.mmm."""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


class VoxReelExporter:
    """Exports session transcript data to JSON, SRT, VTT, ELAN (.eaf), and TXT."""

    @staticmethod
    def export_json(master_data: dict[str, Any], output_path: str | Path) -> Path:
        """Export Master JSON (Appendix C format)."""
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)
        return p

    @staticmethod
    def export_srt(master_data: dict[str, Any], output_path: str | Path) -> Path:
        """Export SubRip (.srt) subtitle file with speaker attribution."""
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        segments = master_data.get("segments", [])
        lines: list[str] = []

        for idx, seg in enumerate(segments, start=1):
            start_str = _format_time_srt(float(seg.get("start", 0.0)))
            end_str = _format_time_srt(float(seg.get("end", 0.0)))
            actor_or_spk = seg.get("actor") or seg.get("speaker") or "Speaker"
            text = seg.get("text", "").strip()

            lines.append(str(idx))
            lines.append(f"{start_str} --> {end_str}")
            lines.append(f"[{actor_or_spk}]: {text}")
            lines.append("")

        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return p

    @staticmethod
    def export_vtt(master_data: dict[str, Any], output_path: str | Path) -> Path:
        """Export WebVTT (.vtt) format with voice tags."""
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        segments = master_data.get("segments", [])
        lines: list[str] = ["WEBVTT", ""]

        for _idx, seg in enumerate(segments, start=1):
            start_str = _format_time_vtt(float(seg.get("start", 0.0)))
            end_str = _format_time_vtt(float(seg.get("end", 0.0)))
            actor_or_spk = seg.get("actor") or seg.get("speaker") or "Speaker"
            text = seg.get("text", "").strip()

            lines.append(f"{start_str} --> {end_str}")
            lines.append(f"<v {actor_or_spk}>{text}</v>")
            lines.append("")

        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return p

    @staticmethod
    def export_txt(master_data: dict[str, Any], output_path: str | Path) -> Path:
        """Export plain text readable transcript."""
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        segments = master_data.get("segments", [])
        lines: list[str] = [
            f"# VoxReel Transcript — {master_data.get('media', {}).get('name', 'Media')}",
            f"# Language: {master_data.get('language', 'en')}",
            "",
        ]

        for seg in segments:
            start_str = _format_time_srt(float(seg.get("start", 0.0)))[:8]
            end_str = _format_time_srt(float(seg.get("end", 0.0)))[:8]
            actor_or_spk = seg.get("actor") or seg.get("speaker") or "Speaker"
            text = seg.get("text", "").strip()
            lines.append(f"[{start_str} - {end_str}] {actor_or_spk}: {text}")

        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return p

    @staticmethod
    def export_elan(master_data: dict[str, Any], output_path: str | Path) -> Path:
        """Export ELAN Annotation File (.eaf XML format)."""
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        media_name = master_data.get("media", {}).get("name", "media.wav")
        segments = master_data.get("segments", [])

        # Build XML
        root = ET.Element(
            "ANNOTATION_DOCUMENT",
            {
                "AUTHOR": "VoxReel 1.0.0",
                "DATE": "2026-09-24T00:00:00+00:00",
                "FORMAT": "3.0",
                "VERSION": "3.0",
                "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            },
        )

        header = ET.SubElement(root, "HEADER", {"MEDIA_FILE": "", "TIME_UNITS": "milliseconds"})
        ET.SubElement(
            header,
            "MEDIA_DESCRIPTOR",
            {
                "MEDIA_URL": f"file:///{media_name}",
                "MIME_TYPE": "audio/x-wav",
                "RELATIVE_MEDIA_URL": f"./{media_name}",
            },
        )

        time_order = ET.SubElement(root, "TIME_ORDER")
        time_slot_map: dict[int, str] = {}
        time_slot_counter = 1

        for seg in segments:
            start_ms = int(round(float(seg.get("start", 0.0)) * 1000))
            end_ms = int(round(float(seg.get("end", 0.0)) * 1000))

            if start_ms not in time_slot_map:
                ts_id = f"ts{time_slot_counter}"
                time_slot_counter += 1
                time_slot_map[start_ms] = ts_id
                ET.SubElement(time_order, "TIME_SLOT", {"TIME_SLOT_ID": ts_id, "TIME_VALUE": str(start_ms)})

            if end_ms not in time_slot_map:
                ts_id = f"ts{time_slot_counter}"
                time_slot_counter += 1
                time_slot_map[end_ms] = ts_id
                ET.SubElement(time_order, "TIME_SLOT", {"TIME_SLOT_ID": ts_id, "TIME_VALUE": str(end_ms)})

        # Group segments by speaker tier
        tiers: dict[str, list[dict[str, Any]]] = {}
        for seg in segments:
            tier_name = seg.get("actor") or seg.get("speaker") or "Speaker"
            tiers.setdefault(tier_name, []).append(seg)

        ann_counter = 1
        for tier_name, tier_segs in tiers.items():
            tier_elem = ET.SubElement(
                root,
                "TIER",
                {
                    "DEFAULT_LOCALE": "en",
                    "LINGUISTIC_TYPE_REF": "default-lt",
                    "TIER_ID": tier_name,
                },
            )

            for s in tier_segs:
                start_ms = int(round(float(s.get("start", 0.0)) * 1000))
                end_ms = int(round(float(s.get("end", 0.0)) * 1000))
                ts1 = time_slot_map[start_ms]
                ts2 = time_slot_map[end_ms]

                ann_id = f"a{ann_counter}"
                ann_counter += 1

                ann_elem = ET.SubElement(tier_elem, "ANNOTATION")
                align_elem = ET.SubElement(
                    ann_elem,
                    "ALIGNABLE_ANNOTATION",
                    {"ANNOTATION_ID": ann_id, "TIME_SLOT_REF1": ts1, "TIME_SLOT_REF2": ts2},
                )
                val_elem = ET.SubElement(align_elem, "ANNOTATION_VALUE")
                val_elem.text = s.get("text", "")

        # Linguistic type
        ET.SubElement(
            root,
            "LINGUISTIC_TYPE",
            {
                "GRAPHIC_REFERENCES": "false",
                "LINGUISTIC_TYPE_ID": "default-lt",
                "TIME_ALIGNABLE": "true",
            },
        )

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(str(p), encoding="utf-8", xml_declaration=True)
        return p
