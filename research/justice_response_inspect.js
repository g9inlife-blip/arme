/*
 * Runtime response inspector v1.0
 * Purpose:
 *   ProccessRequestRes(response) 진입 시 response의 실제 IL2CPP class와
 *   instance field 이름/offset/type/value를 확인한다.
 *
 * 기존 justice_hook.js와 독립 실행 가능.
 * Usage:
 *   frida ... -l justice_hook.js -l justice_response_inspect.js
 */
'use strict';

(function () {
    const LIB_NAME = 'libil2cpp.so';
    let api = null;

    function initApi() {
        const maps = File.readAllText('/proc/self/maps');
        let base = null, path = null;
        for (const line of maps.split('\n')) {
            if (line.indexOf(LIB_NAME) < 0) continue;
            const p = line.trim().split(/\s+/);
            if (p.length < 6) continue;
            const range = p[0].split('-');
            if (p[2] === '00000000' && p[1].indexOf('r') === 0) {
                base = ptr('0x' + range[0]);
                path = p[5];
                break;
            }
        }
        if (!base) throw new Error(LIB_NAME + ' not found');

        const buf = File.readAllBytes(path);
        const dv = new DataView(buf);
        const u8 = new Uint8Array(buf);
        function u16(o) { return dv.getUint16(o, true); }
        function u32(o) { return dv.getUint32(o, true); }
        function u64(o) { return Number(dv.getBigUint64(o, true)); }
        if (u32(0) !== 0x464c457f) throw new Error('not ELF');

        const phoff = u64(0x20), phnum = u16(0x38);
        const loads = [];
        let dynOff = -1, dynSize = 0;
        for (let i = 0; i < phnum; i++) {
            const ph = phoff + i * 56;
            const type = u32(ph);
            const po = u64(ph + 8), pv = u64(ph + 16), fs = u64(ph + 32);
            if (type === 1) loads.push({vaddr:pv, offset:po, filesz:fs});
            if (type === 2) { dynOff = po; dynSize = fs; }
        }
        function v2o(v) {
            for (const s of loads)
                if (v >= s.vaddr && v < s.vaddr + s.filesz)
                    return s.offset + (v - s.vaddr);
            return -1;
        }
        let symV=0,strV=0,strSz=0,ent=24;
        for (let o=dynOff; o<dynOff+dynSize; o+=16) {
            const tag=dv.getBigInt64(o,true), val=u64(o+8);
            if(tag===6n) symV=val;
            else if(tag===5n) strV=val;
            else if(tag===10n) strSz=val;
            else if(tag===11n) ent=val;
            else if(tag===0n) break;
        }
        const so=v2o(symV), sto=v2o(strV);
        function cstr(o) {
            let e=o;
            while(e<u8.length && u8[e]!==0)e++;
            let s='';
            for(let i=o;i<e;i++)s+=String.fromCharCode(u8[i]);
            return s;
        }
        function exp(name) {
            for(let i=0;i<300000;i++){
                const o=so+i*ent;
                if(o+24>u8.length)break;
                const n=u32(o), v=u64(o+8);
                if(!n||!v||n>=strSz)continue;
                if(cstr(sto+n)===name)return base.add(v);
            }
            throw new Error('export not found: '+name);
        }

        api = {
            domain_get:new NativeFunction(exp('il2cpp_domain_get'),'pointer',[]),
            domain_get_assemblies:new NativeFunction(exp('il2cpp_domain_get_assemblies'),'pointer',['pointer','pointer']),
            assembly_get_image:new NativeFunction(exp('il2cpp_assembly_get_image'),'pointer',['pointer']),
            image_get_name:new NativeFunction(exp('il2cpp_image_get_name'),'pointer',['pointer']),
            class_from_name:new NativeFunction(exp('il2cpp_class_from_name'),'pointer',['pointer','pointer','pointer']),
            class_get_methods:new NativeFunction(exp('il2cpp_class_get_methods'),'pointer',['pointer','pointer']),
            method_get_name:new NativeFunction(exp('il2cpp_method_get_name'),'pointer',['pointer']),
            method_get_param_count:new NativeFunction(exp('il2cpp_method_get_param_count'),'uint32',['pointer']),
            method_get_param:new NativeFunction(exp('il2cpp_method_get_param'),'pointer',['pointer','uint32']),
            type_get_name:new NativeFunction(exp('il2cpp_type_get_name'),'pointer',['pointer']),
            method_get_return_type:new NativeFunction(exp('il2cpp_method_get_return_type'),'pointer',['pointer']),
            class_get_name:new NativeFunction(exp('il2cpp_class_get_name'),'pointer',['pointer']),
            class_get_fields:new NativeFunction(exp('il2cpp_class_get_fields'),'pointer',['pointer','pointer']),
            field_get_name:new NativeFunction(exp('il2cpp_field_get_name'),'pointer',['pointer']),
            field_get_type:new NativeFunction(exp('il2cpp_field_get_type'),'pointer',['pointer']),
            field_get_offset:new NativeFunction(exp('il2cpp_field_get_offset'),'uint32',['pointer']),
            object_get_class:new NativeFunction(exp('il2cpp_object_get_class'),'pointer',['pointer']),
        };
    }

    function findMethod(className, methodName, paramCount) {
        const domain=api.domain_get();
        const cp=Memory.alloc(Process.pointerSize);
        const asms=api.domain_get_assemblies(domain,cp);
        const n=cp.readU32();
        const ns=Memory.allocUtf8String('');
        const cn=Memory.allocUtf8String(className);
        for(let i=0;i<n;i++){
            try{
                const img=api.assembly_get_image(asms.add(i*Process.pointerSize).readPointer());
                const k=api.class_from_name(img,ns,cn);
                if(k.isNull())continue;
                const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
                while(true){
                    const m=api.class_get_methods(k,it);
                    if(m.isNull())break;
                    if(api.method_get_name(m).readCString()!==methodName)continue;
                    if(api.method_get_param_count(m)!==paramCount)continue;
                    return {fn:m.readPointer(),klass:k};
                }
            }catch(e){}
        }
        return null;
    }

    function safeValue(obj, off, typeName) {
        try {
            const p=obj.add(off);
            if(typeName.indexOf('System.Int32')>=0 || typeName==='int')
                return String(p.readS32());
            if(typeName.indexOf('System.UInt32')>=0)
                return String(p.readU32());
            if(typeName.indexOf('System.Int64')>=0)
                return String(p.readS64());
            if(typeName.indexOf('System.UInt64')>=0)
                return String(p.readU64());
            if(typeName==='System.Boolean' || typeName==='bool')
                return String(p.readU8()!==0);
            const q=p.readPointer();
            return q.isNull() ? 'null' : q.toString();
        } catch(e) { return '<read-failed>'; }
    }

    function inspect(obj) {
        if(!obj || obj.isNull()) return;
        try {
            const k=api.object_get_class(obj);
            const name=api.class_get_name(k).readCString();
            console.log('[RESP_CLASS] obj='+obj+' class='+name);

            const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
            let count=0;
            while(count<200){
                const f=api.class_get_fields(k,it);
                if(f.isNull())break;
                const fn=api.field_get_name(f).readCString();
                let tn='?';
                try { tn=api.type_get_name(api.field_get_type(f)).readCString(); } catch(e){}
                const off=api.field_get_offset(f);
                // Static fields have special offsets; only dump plausible instance fields.
                if(off<0x1000 && fn!=='') {
                    console.log('[RESP_FIELD] '+fn+' @+0x'+off.toString(16)+' type='+tn+' value='+safeValue(obj,off,tn));
                }
                count++;
            }
            console.log('[RESP_FIELD_END] count='+count);
        } catch(e) {
            console.log('[RESP_INSPECT_ERR] '+e.message);
        }
    }

    function main() {
        try {
            initApi();
            console.log('[+] response inspector v1.0 initialized');
            const m=findMethod('DataCenter','ProccessRequestRes',3);
            if(!m){
                console.log('[!] DataCenter.ProccessRequestRes(3 params) not found');
                return;
            }
            console.log('[+] Inspecting DataCenter.ProccessRequestRes @ '+m.fn);
            Interceptor.attach(m.fn,{
                onEnter(args){
                    const response=args[1];
                    if(!response || response.isNull()){
                        console.log('[RESP_CLASS] response=null');
                        return;
                    }
                    inspect(response);
                }
            });
        } catch(e) {
            console.log('[!] response inspector failed: '+e.message);
        }
    }
    main();
})();
