"""Generate an original 1024px app icon with no external dependencies."""
from pathlib import Path
import json,math,struct,zlib
W=1024
def rgba(x,y):
    dx=(x-512)/400;dy=(y-505)/400;d=math.hypot(dx,dy)
    bg=(5,19,39)
    if d<0.91:
        c=(10,75,145) if d<0.89 else (22,168,232)
        if abs(dx)<0.025 or abs(dy)<0.023 or abs(dy-math.sin(dx*5)*0.10)<0.018:
            c=(80,220,255)
        for k in [-0.58,0.58]:
            if abs(dx-k)<0.014 and abs(dy)<0.62:c=(45,170,235)
        return bytes((*c,255))
    return bytes((*bg,255))
def chunk(tag,body):
    payload=tag+body
    return struct.pack(">I",len(body))+payload+struct.pack(">I",zlib.crc32(payload)&0xffffffff)
def main():
    dest=Path("ios/WorldPulse/Assets.xcassets/AppIcon.appiconset")
    dest.mkdir(parents=True,exist_ok=True)
    compressor=zlib.compressobj(7)
    blocks=[]
    for y in range(W):
        row=b'\x00'+b''.join(rgba(x,y) for x in range(W))
        blocks.append(compressor.compress(row))
    blocks.append(compressor.flush())
    (dest/"AppIcon.png").write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">2I5B",W,W,8,6,0,0,0))+chunk(b"IDAT",b"".join(blocks))+chunk(b"IEND",b""))
    (dest/"Contents.json").write_text(json.dumps({"images":[{"filename":"AppIcon.png","idiom":"universal","platform":"ios","size":"1024x1024"}],"info":{"author":"xcode","version":1}}))
if __name__=="__main__":main()
