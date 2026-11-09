"""Experimental keyed pixel watermark for provenance, never DRM or an AI command.

One luminance DCT coefficient per textured8x8 block carries a repeated bit.
The128-bit packet is an opaque64-bit asset ID and its truncated64-bit HMAC.
Detection requires the secret key and original pixel grid. Crop, rescale or
deliberate edits may erase it. No C2PA signature or copyright certification.
"""
from __future__ import annotations

import hashlib
import hmac
import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

VERSION = 'toon-local-dct-qim-v1'
STEP = 16
BASIS = tuple(.25*math.cos((2*x+1)*2*math.pi/16)*math.cos((2*y+1)*math.pi/16)
              for y in range(8) for x in range(8))
RESTRICTIONS = ('No unauthorized reproduction, redistribution, AI training or AI-based re-creation. '
                'Subject to applicable rights and law. This is a use request, not technical access control.')


def load_key(path, *, create=False):
    """Keep the key local; callers must exclude it from archives and tool output."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refuse linked watermark key')
    if create and not path.exists():
        import secrets
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(secrets.token_bytes(32))
    key = path.read_bytes()
    if len(key) != 32:
        raise ValueError('Watermark key must contain32 bytes')
    return key


def _packet(key, asset_id):
    if len(key) != 32 or len(asset_id) != 8:
        raise ValueError('Require32-byte key and8-byte opaque asset ID')
    return asset_id + hmac.digest(key,b'packet-v1:'+asset_id,'sha256')[:8]


def _blocks(image, key):
    gray = image.convert('L')
    pixels = gray.load()
    for y in range(0,image.height-7,8):
        for x in range(0,image.width-7,8):
            values = [pixels[x+dx,y+dy] for dy in range(8) for dx in range(8)]
            mean = sum(values)/64
            if max(values)-min(values) < 32 or not 24 <= mean <= 232:
                continue
            index = int.from_bytes(hmac.digest(key,f'grid-v1:{x}:{y}'.encode(),'sha256')[:2],'big') % 128
            coefficient = sum(v*b for v,b in zip(values,BASIS))
            yield x,y,index,coefficient


def embed(image, key, asset_id, *, protected_top=0):
    if image.mode != 'RGB':
        raise ValueError('Watermark input must be an explicit RGB delivery copy')
    if type(protected_top) is not int or not 0 <= protected_top <= image.height:
        raise ValueError('protected_top must stay inside the image')
    packet = _packet(key,asset_id)
    bits = [(b>>shift)&1 for b in packet for shift in range(7,-1,-1)]
    output = image.copy()
    pixels = output.load()
    counts = [0]*128
    for x,y,index,coefficient in _blocks(image,key):
        if y < protected_top:
            continue
        bit = bits[index]
        target = (2*round((coefficient/STEP-bit)/2)+bit)*STEP
        delta = target-coefficient
        for i,basis in enumerate(BASIS):
            dx,dy = i%8,i//8
            adjustment = round(delta*basis)
            if adjustment:
                pixels[x+dx,y+dy] = tuple(max(0,min(255,v+adjustment)) for v in pixels[x+dx,y+dy])
        counts[index] += 1
    if min(counts) < 2:
        raise ValueError('Insufficient textured blocks for a full watermark; no marked file issued')
    result = detect(output,key)
    if not result['detected'] or result['asset_id'] != asset_id.hex():
        raise ValueError('Pixel watermark roundtrip failed; no marked file issued')
    return output,dict(version=VERSION,asset_id=asset_id.hex(),eligible_blocks=sum(counts),
                       minimum_repetitions=min(counts),roundtrip_verified=True,
                       enforcement='none',c2pa_signed=False)


def detect(image,key):
    if len(key) != 32:
        raise ValueError('Invalid watermark key')
    counts = [0]*128
    votes = [0]*128
    for _,_,index,coefficient in _blocks(image.convert('RGB'),key):
        bit = round(coefficient/STEP) % 2
        votes[index] += 1 if bit else -1
        counts[index] += 1
    if min(counts) < 2 or any(v==0 for v in votes):
        return dict(detected=False,asset_id=None,reason='insufficient_or_tied_pixel_votes')
    bits = [int(v>0) for v in votes]
    packet = bytes(sum(bits[i+j] << (7-j) for j in range(8)) for i in range(0,128,8))
    valid = hmac.compare_digest(_packet(key,packet[:8]),packet)
    return dict(detected=valid,asset_id=packet[:8].hex() if valid else None,
                reason='authenticated_pixel_packet' if valid else 'packet_authentication_failed')


def xmp(asset_id):
    """Unsigned standard XMP source/use metadata; no hidden agent instructions."""
    return (f'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            f'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            f'<rdf:Description rdf:about="" xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/" '
            f'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            f'xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
            f'xmlns:toon="urn:toon-lab:provenance:1/" '
            f'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/compositeSynthetic" '
            f'toon:AssetID="{escape(asset_id)}" toon:WatermarkVersion="{VERSION}">'
            f'<xmpRights:UsageTerms><rdf:Alt><rdf:li xml:lang="x-default">{escape(RESTRICTIONS)}</rdf:li>'
            f'</rdf:Alt></xmpRights:UsageTerms>'
            f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">AI-generated scene artwork with local lettering and assembly; '
            f'local provenance marker, not signed C2PA or legal ownership proof.</rdf:li></rdf:Alt></dc:description>'
            f'</rdf:Description></rdf:RDF></x:xmpmeta>').encode()


if __name__=='__main__':
    import argparse
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['detect'])
    parser.add_argument('image',type=Path)
    parser.add_argument('--key',type=Path,default=Path(__file__).resolve().parents[1]/'workspace/_private/provenance_watermark.key')
    args=parser.parse_args()
    result=detect(Image.open(args.image),load_key(args.key))
    print(json.dumps(dict(version=VERSION,**result,enforcement='none',rights_certification=False)))
