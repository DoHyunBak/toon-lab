"""Losslessly recompress PNG IDAT data; preserve every other chunk verbatim."""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path


SIGNATURE = b"\x89PNG\r\n\x1a\n"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload)))


def inspect_png(data):
    if not data.startswith(SIGNATURE):
        raise ValueError("Input is not PNG")
    parts, offset = [], 8
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        size = struct.unpack_from(">I", data, offset)[0]
        end = offset + 12 + size
        if end > len(data):
            raise ValueError("Truncated PNG payload")
        kind, payload = data[offset + 4:offset + 8], data[offset + 8:end - 4]
        if zlib.crc32(kind + payload) != struct.unpack_from(">I", data, end - 4)[0]:
            raise ValueError("PNG chunk CRC mismatch")
        parts.append((kind, payload, data[offset:end]))
        offset = end
        if kind == b"IEND":
            break
    kinds = [p[0] for p in parts]
    if (offset != len(data) or not parts or kinds[0] != b"IHDR"
            or kinds[-1] != b"IEND" or parts[-1][1] or kinds.count(b"IHDR") != 1
            or b"IDAT" not in kinds):
        raise ValueError("Invalid PNG structure or trailing bytes")
    if any(k in kinds for k in (b"acTL", b"fcTL", b"fdAT")):
        raise ValueError("Animated PNG is not supported")
    indices = [i for i, kind in enumerate(kinds) if kind == b"IDAT"]
    if indices != list(range(indices[0], indices[-1] + 1)):
        raise ValueError("Non-consecutive IDAT chunks")
    if len(parts[0][1]) != 13:
        raise ValueError("Invalid IHDR")
    width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", parts[0][1])
    allowed = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8),
               4: (8, 16), 6: (8, 16)}
    if (not width or not height or depth not in allowed.get(color, ())
            or comp or filt or interlace not in (0, 1)):
        raise ValueError("Unsupported or invalid IHDR")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    passes = [(0, 0, 1, 1)] if not interlace else [
        (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
        (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
    rows, expected = [], 0
    for x, y, dx, dy in passes:
        pw, ph = max(0, (width - x + dx - 1) // dx), max(0, (height - y + dy - 1) // dy)
        if pw and ph:
            stride = 1 + (pw * channels * depth + 7) // 8
            rows.append((stride, ph))
            expected += stride * ph
    # Bound memory for local full-strip processing; never disable Pillow safety globally.
    if expected > 512 * 1024 * 1024:
        raise ValueError("Decoded scanlines exceed 512 MiB limit; split the delivery first")
    packed = b"".join(p[1] for p in parts if p[0] == b"IDAT")
    decoder = zlib.decompressobj()
    scanlines = decoder.decompress(packed, expected + 1)
    if (len(scanlines) != expected or not decoder.eof
            or decoder.unused_data or decoder.unconsumed_tail):
        raise ValueError("Invalid PNG compressed stream or scanline length")
    pos = 0
    for stride, count in rows:
        for _ in range(count):
            if scanlines[pos] > 4:
                raise ValueError("Invalid PNG filter")
            pos += stride
    return parts, scanlines, (width, height)


def optimize(data):
    parts, raw, dimensions = inspect_png(data)
    best = data
    strategy_name = "original_retained"
    for name, strategy in (("default", zlib.Z_DEFAULT_STRATEGY), ("filtered", zlib.Z_FILTERED)):
        encoder = zlib.compressobj(9, zlib.DEFLATED, 15, 8, strategy)
        packed = encoder.compress(raw) + encoder.flush()
        output, inserted = [SIGNATURE], False
        for kind, _, original in parts:
            if kind == b"IDAT":
                if not inserted:
                    output.append(chunk(b"IDAT", packed))
                    inserted = True
            else:
                output.append(original)
        candidate = b"".join(output)
        if len(candidate) < len(best):
            best, strategy_name = candidate, name
    after, decoded, after_dimensions = inspect_png(best)
    if (raw != decoded or dimensions != after_dimensions
            or [p[2] for p in parts if p[0] != b"IDAT"]
            != [p[2] for p in after if p[0] != b"IDAT"]):
        raise ValueError("Lossless verification failed")
    return best, {
        "schema_version": 1, "method": "stdlib_zlib_idat_recompression",
        "strategy": strategy_name, "width": dimensions[0], "height": dimensions[1],
        "source_bytes": len(data), "output_bytes": len(best),
        "saved_bytes": len(data) - len(best),
        "saved_percent": round((1 - len(best) / len(data)) * 100, 3),
        "source_sha256": sha256(data), "output_sha256": sha256(best),
        "verification": {"filtered_scanlines_identical": True,
                         "non_idat_chunks_identical": True,
                         "png_crc_and_zlib_valid": True,
                         "pixel_equivalence": "identical IHDR, scanlines, palette and transparency"},
        "scope": "Local lossless compression only; no artwork approval or Drive readback",
    }


def compress_file(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    report_path = output.with_suffix(output.suffix + ".compression.json")
    if source == output or output.exists() or report_path.exists():
        raise ValueError("Source overwrite or existing output/report is forbidden")
    data = source.read_bytes()
    result, report = optimize(data)
    report.update(source=str(source), output=str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also protects against another session creating this target.
    with output.open("xb") as stream:
        stream.write(result)
    if output.read_bytes() != result:
        raise ValueError("Written output verification failed")
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="New PNG path; never overwritten")
    args = parser.parse_args()
    try:
        print(json.dumps(compress_file(args.source, args.output), ensure_ascii=False, indent=2))
    except (OSError, ValueError, zlib.error) as exc:
        parser.exit(2, f"PNG compression failed: {exc}\n")


if __name__ == "__main__":
    main()
