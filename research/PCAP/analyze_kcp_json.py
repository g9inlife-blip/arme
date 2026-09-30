#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze Wireshark/PCAPdroid JSON exported game KCP traffic.

Game-specific KCP:
  conv uint64, cmd u8, frg u8, wnd u16, ts u32, sn u32, una u32, len u32
  => 28-byte header

Application:
  [flags:1][IV:16][AES-128-CBC ciphertext]
  flags 0x80 = encrypted
  flags 0xC4 = encrypted/compressed
"""
from __future__ import annotations
import argparse, gzip, json, struct
from collections import defaultdict
from pathlib import Path

try:
    from Crypto.Cipher import AES
except ImportError:
    raise SystemExit("PyCryptodome required: pip install pycryptodome")

KEY = bytes.fromhex("44f5f445808615fe1b2e224c5e05e718")
KCP_HDR = 28

def hx(s):
    return bytes.fromhex(s.replace(":", ""))

def varint(data, off):
    v=0; shift=0
    while off < len(data):
        b=data[off]; off+=1
        v |= (b & 0x7f) << shift
        if not b & 0x80: return v,off
        shift += 7
        if shift > 63: break
    raise ValueError("bad varint")

def protobuf_top(data):
    out=[]
    off=0
    while off < len(data):
        start=off
        tag,off=varint(data,off)
        field=tag>>3; wire=tag&7
        item={"field":field,"wire":wire,"offset":start}
        if wire==0:
            v,off=varint(data,off); item["value"]=v
        elif wire==1:
            item["value_hex"]=data[off:off+8].hex(); off+=8
        elif wire==2:
            n,off=varint(data,off); b=data[off:off+n]; off+=n
            item["length"]=n; item["prefix_hex"]=b[:64].hex()
            if n and b[:2]==b"\x1f\x8b":
                try:
                    item["gzip"]="yes"; item["gzip_uncompressed_bytes"]=len(gzip.decompress(b))
                except Exception: pass
        elif wire==5:
            item["value_hex"]=data[off:off+4].hex(); off+=4
        else:
            break
        out.append(item)
    return out

def packet_layers(obj):
    return obj.get("_source",{}).get("layers",{})

def get_hex(layers, proto):
    p=layers.get(proto,{})
    for k,v in p.items():
        if k.endswith(".payload") and isinstance(v,(str,list)):
            return v[0] if isinstance(v,list) else v
    return None

def ip4(layers,key):
    return layers.get("ip",{}).get(key)

def port(layers,proto,key):
    v=layers.get(proto,{}).get(key)
    return int(v,0) if isinstance(v,str) else v

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("json",type=Path)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    raw=json.loads(args.json.read_text(encoding="utf-8"))
    packets=raw if isinstance(raw,list) else raw.get("packets",[])
    out=args.out or args.json.with_name(args.json.stem+"_kcp")
    out.mkdir(parents=True,exist_ok=True)

    segments=[]
    for p in packets:
        l=packet_layers(p); u=l.get("udp",{})
        payload=get_hex(l,"udp")
        if not payload: continue
        b=hx(payload)
        if len(b)<KCP_HDR: continue
        conv,cmd,frg,wnd,ts,sn,una,n=struct.unpack_from("<QBBHIIII",b,0)
        if cmd != 0x51 or n > len(b)-KCP_HDR: continue
        app=b[KCP_HDR:KCP_HDR+n]
        segments.append({
            "packet":int(l.get("frame",{}).get("frame.number",0)),
            "src":ip4(l,"ip.src"),"sport":port(l,"udp","udp.srcport"),
            "dst":ip4(l,"ip.dst"),"dport":port(l,"udp","udp.dstport"),
            "conv":conv,"frg":frg,"sn":sn,"una":una,"app":app
        })

    # Reassemble each direction/message. frg=1..0 in this protocol.
    groups=defaultdict(list)
    for s in segments:
        direction=(s["conv"],s["src"],s["sport"],s["dst"],s["dport"])
        groups[direction].append(s)

    results=[]
    for direction,ss in groups.items():
        ss.sort(key=lambda x:x["sn"])
        cur=[]; expected=None
        def flush(cur):
            if not cur: return
            data=b"".join(x["app"] for x in sorted(cur,key=lambda y:y["sn"]))
            first=cur[0]
            rec={"packets":[x["packet"] for x in cur],"conv":first["conv"],
                 "src":first["src"],"sport":first["sport"],
                 "dst":first["dst"],"dport":first["dport"],
                 "bytes":len(data),"hex_prefix":data[:96].hex()}
            if len(data)>=17 and data[0] in (0x80,0xc0,0xc4):
                rec["flags"]=data[0]; rec["iv"]=data[1:17].hex()
                ct=data[17:]
                rec["ciphertext_bytes"]=len(ct)
                if len(ct)%16==0:
                    try:
                        pt=AES.new(KEY,AES.MODE_CBC,data[1:17]).decrypt(ct)
                        pad=pt[-1]
                        if 1<=pad<=16 and pt.endswith(bytes([pad])*pad):
                            pt=pt[:-pad]
                        rec["decrypt"]="ok"; rec["plaintext_bytes"]=len(pt)
                        rec["plaintext_prefix"]=pt[:128].hex()
                        rec["protobuf"]=protobuf_top(pt)
                        if pt[:2]==b"\x1f\x8b":
                            dec=gzip.decompress(pt); rec["gzip_bytes"]=len(dec)
                            rec["gzip_prefix"]=dec[:128].hex()
                            rec["gzip_protobuf"]=protobuf_top(dec)
                    except Exception as e:
                        rec["decrypt"]="failed"; rec["error"]=str(e)
            results.append(rec)
        for s in ss:
            if not cur:
                cur=[s]
            elif s["frg"] != 0:
                cur.append(s)
            else:
                cur.append(s); flush(cur); cur=[]
        flush(cur)

    results.sort(key=lambda r:min(r["packets"]))
    (out/"messages.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/"messages.txt").open("w",encoding="utf-8") as f:
        for r in results:
            f.write(f'packets={r["packets"]} {r["src"]}:{r["sport"]}->{r["dst"]}:{r["dport"]} bytes={r["bytes"]}\n')
            f.write(f'  flags={r.get("flags")} decrypt={r.get("decrypt")} prefix={r.get("plaintext_prefix", "")[:80]}\n')
            for x in r.get("protobuf",[]): f.write(f'  field={x}\n')
            for x in r.get("gzip_protobuf",[]): f.write(f'  gzip_field={x}\n')
    print(f"[+] KCP segments={len(segments)} messages={len(results)} out={out}")

if __name__=="__main__":
    main()
