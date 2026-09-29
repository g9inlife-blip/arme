/**
 * JusticeSchool (com.Alioth.JusticeSchool.cn) - Login Hook Script v4.3
 *
 * v4.3: String.Join/MD5HashString 후킹으로 Sign 최종 입력 원문 추적 + namespace-aware System lookup
 *
 * NO frida-il2cpp-bridge, NO frida-compile needed.
 * Resolves IL2CPP exports by parsing /proc/self/maps + ELF directly,
 * because Frida's module enumeration misses Houdini-translated ARM libs
 * on x86_64 emulators.
 *
 * Hooks:
 *  - ProtocolGame_HttpRequest.V4_POST_Login(app_key, content, apiName)
 *  - ProtocolGame_HttpRequest.Sign(content, apiName)
 *  - ProtocolGame_HttpRequest.GetDefaultParams()
 *  - ProtocolGame_HttpRequest.V3_POST_AllInOne(app_key)
 *
 * Usage:
 *   frida -U -p <PID> -l justice_hook.js
 *   (attach AFTER the game has loaded the Unity engine)
 *
 * Output: [SIGN_DATA] lines carry Sign input/output pairs for
 *         reverse-engineering the signature algorithm.
 */

'use strict';

// Parameter names (from static analysis, NEWVERSION-003)
const PARAMS = {
    'V4_POST_Login': ['app_key', 'content', 'apiName'],
    'Sign': ['content', 'apiName'],
    'GetDefaultParams': [],
    'V3_POST_AllInOne': ['app_key'],
};
const CLASS_NAME = 'ProtocolGame_HttpRequest';
const LIB_NAME = 'libil2cpp.so';

// ---------- helpers ----------

function readIl2cppString(ptr) {
    if (ptr.isNull()) return '(null)';
    try {
        // Validate pointer is readable
        const klass = ptr.readPointer();
        if (klass.isNull()) return '(invalid klass)';
        // Il2CppString (64-bit): [klass(8)][monitor(8)][length(4)][chars...]
        const length = ptr.add(16).readU32();
        if (length > 10000) {
            // Dump first bytes for diagnosis
            let hex = '';
            try {
                for (let i = 0; i < 32; i++) {
                    hex += ptr.add(i).readU8().toString(16).padStart(2, '0') + ' ';
                }
            } catch (e) { hex = 'unreadable'; }
            return `(invalid string, length=${length}, ptr=${ptr}, hex=[${hex}])`;
        }
        return ptr.add(20).readUtf16String(length);
    } catch (e) {
        return `<unreadable:${e.message}>`;
    }
}

function trunc(s, maxLen) {
    maxLen = maxLen || 500;
    if (s === null || s === undefined) return '(null)';
    s = String(s);
    if (s.length > maxLen) {
        return s.substring(0, maxLen) + `...[truncated ${s.length} chars total]`;
    }
    return s;
}

function readIl2cppArrayStrings(arrPtr, maxItems) {
    const out = [];
    try {
        if (arrPtr.isNull()) return out;
        const len = arrPtr.add(24).readU32();
        const n = Math.min(len, maxItems || 100);
        for (let i = 0; i < n; i++) {
            const itemPtr = arrPtr.add(32 + i * Process.pointerSize).readPointer();
            out.push(itemPtr.isNull() ? '(null)' : readIl2cppString(itemPtr));
        }
        if (len > n) out.push('(truncated ' + len + ' items total)');
    } catch (e) { out.push('<array read failed: ' + e.message + '>'); }
    return out;
}

// ---------- ELF-based export resolution ----------
// Finds the module base via /proc/self/maps and resolves dynamic
// symbols by parsing the ELF file directly.

function findModuleBase(libFileName) {
    const maps = File.readAllText('/proc/self/maps');
    for (const line of maps.split('\n')) {
        if (line.indexOf(libFileName) === -1) continue;
        // format: addr_start-addr_end perms offset dev inode pathname
        const parts = line.trim().split(/\s+/);
        if (parts.length < 6) continue;
        const range = parts[0].split('-');
        const offset = parts[2];
        if (offset === '00000000' && parts[1].indexOf('r') === 0) {
            return { base: ptr('0x' + range[0]), path: parts[5] };
        }
    }
    return null;
}

function resolveElfExport(modulePath, baseAddr, symbolName) {
    const buf = File.readAllBytes(modulePath);
    const dv = new DataView(buf);
    const u8 = new Uint8Array(buf);

    function u16(off) { return dv.getUint16(off, true); }
    function u32(off) { return dv.getUint32(off, true); }
    function u64(off) { return Number(dv.getBigUint64(off, true)); }

    // ELF header
    if (u32(0) !== 0x464C457F) throw new Error('not an ELF file');
    const e_phoff = u64(0x20);
    const e_phnum = u16(0x38);

    // Collect PT_LOAD segments for vaddr -> file offset translation,
    // and locate PT_DYNAMIC.
    const loads = [];
    let dynOff = -1, dynSize = 0;
    for (let i = 0; i < e_phnum; i++) {
        const ph = e_phoff + i * 56;
        const p_type = u32(ph);
        const p_offset = u64(ph + 8);
        const p_vaddr = u64(ph + 16);
        const p_filesz = u64(ph + 32);
        if (p_type === 1) { // PT_LOAD
            loads.push({ vaddr: p_vaddr, offset: p_offset, filesz: p_filesz });
        } else if (p_type === 2) { // PT_DYNAMIC
            dynOff = p_offset;
            dynSize = p_filesz;
        }
    }
    if (dynOff < 0) throw new Error('no PT_DYNAMIC');

    function vaddrToOffset(vaddr) {
        for (const s of loads) {
            if (vaddr >= s.vaddr && vaddr < s.vaddr + s.filesz) {
                return s.offset + (vaddr - s.vaddr);
            }
        }
        return -1;
    }

    // Parse dynamic entries
    let symtabV = 0, strtabV = 0, strsz = 0, syment = 24;
    for (let off = dynOff; off < dynOff + dynSize; off += 16) {
        const tag = dv.getBigInt64(off, true);
        const val = u64(off + 8);
        if (tag === 6n) symtabV = val;          // DT_SYMTAB
        else if (tag === 5n) strtabV = val;     // DT_STRTAB
        else if (tag === 10n) strsz = val;      // DT_STRSZ
        else if (tag === 11n) syment = val;     // DT_SYMENT
        else if (tag === 0n) break;             // DT_NULL
    }
    if (!symtabV || !strtabV || !strsz) throw new Error('missing dynamic info');

    const symtabOff = vaddrToOffset(symtabV);
    const strtabOff = vaddrToOffset(strtabV);
    if (symtabOff < 0 || strtabOff < 0) throw new Error('vaddr translation failed');

    function readCString(off) {
        let end = off;
        while (end < u8.length && u8[end] !== 0) end++;
        let s = '';
        for (let i = off; i < end; i++) s += String.fromCharCode(u8[i]);
        return s;
    }

    // Linear scan of dynamic symbols
    const maxSyms = 200000;
    for (let i = 0; i < maxSyms; i++) {
        const so = symtabOff + i * syment;
        if (so + 24 > u8.length) break;
        const st_name = u32(so);
        const st_value = u64(so + 8);
        if (st_name === 0 || st_value === 0) continue;
        if (st_name >= strsz) continue;
        const name = readCString(strtabOff + st_name);
        if (name === symbolName) {
            return baseAddr.add(st_value);
        }
        // Heuristic stop: after the null-heavy tail begins we keep going a bit
        if (i > 0 && st_name === 0 && st_value === 0 && i > 50000) break;
    }
    return ptr(0);
}

// ---------- raw IL2CPP API (no bridge) ----------

let api = null;
let il2cppBase = null;

function initApi() {
    const mod = findModuleBase(LIB_NAME);
    if (!mod) throw new Error(LIB_NAME + ' not found in /proc/self/maps');
    il2cppBase = mod.base;
    console.log(`[*] ${LIB_NAME} base @ ${il2cppBase} (${mod.path})`);

    const exp = (n) => {
        const addr = resolveElfExport(mod.path, mod.base, n);
        if (addr.isNull()) throw new Error('export not found: ' + n);
        return addr;
    };
    api = {
        domain_get: new NativeFunction(exp('il2cpp_domain_get'), 'pointer', []),
        domain_get_assemblies: new NativeFunction(exp('il2cpp_domain_get_assemblies'), 'pointer', ['pointer', 'pointer']),
        assembly_get_image: new NativeFunction(exp('il2cpp_assembly_get_image'), 'pointer', ['pointer']),
        image_get_name: new NativeFunction(exp('il2cpp_image_get_name'), 'pointer', ['pointer']),
        class_from_name: new NativeFunction(exp('il2cpp_class_from_name'), 'pointer', ['pointer', 'pointer', 'pointer']),
        class_get_methods: new NativeFunction(exp('il2cpp_class_get_methods'), 'pointer', ['pointer', 'pointer']),
        method_get_name: new NativeFunction(exp('il2cpp_method_get_name'), 'pointer', ['pointer']),
        method_get_param_count: new NativeFunction(exp('il2cpp_method_get_param_count'), 'uint32', ['pointer']),
        method_get_param: new NativeFunction(exp('il2cpp_method_get_param'), 'pointer', ['pointer', 'uint32']),
        method_get_return_type: new NativeFunction(exp('il2cpp_method_get_return_type'), 'pointer', ['pointer']),
        type_get_name: new NativeFunction(exp('il2cpp_type_get_name'), 'pointer', ['pointer']),
        class_get_field_from_name: new NativeFunction(exp('il2cpp_class_get_field_from_name'), 'pointer', ['pointer', 'pointer']),
        field_get_offset: new NativeFunction(exp('il2cpp_field_get_offset'), 'uint32', ['pointer']),
        object_get_class: new NativeFunction(exp('il2cpp_object_get_class'), 'pointer', ['pointer']),
        class_get_name: new NativeFunction(exp('il2cpp_class_get_name'), 'pointer', ['pointer']),
    };
}

// Parse Dictionary<string,string> by reading its _entries array
// v4.1 fix: array max_length is at offset 24 (not 16). Scan for valid entry.
function readDictionary(dictPtr) {
    try {
        if (dictPtr.isNull()) return '(null dictionary)';
        const klass = api.object_get_class(dictPtr);
        const entriesField = api.class_get_field_from_name(klass, Memory.allocUtf8String('_entries'));
        if (entriesField.isNull()) return `(no _entries field)`;
        const entriesOffset = api.field_get_offset(entriesField);
        const entriesArr = dictPtr.add(entriesOffset).readPointer();
        if (entriesArr.isNull()) return '(null entries)';
        // Il2CppArray layout: klass(8) + monitor(8) + bounds(8) + max_length(8) + data
        // bounds=NULL at +16, max_length at +24 (confirmed from v4 debug: len@24=7)
        const maxLen = entriesArr.add(24).readU32();
        if (maxLen > 1000) return `(suspicious maxLen ${maxLen})`;
        // Dictionary._count (actual used entries) - try offset right after _entries ptr
        let dictCount = maxLen;
        try {
            const countField = api.class_get_field_from_name(klass, Memory.allocUtf8String('_count'));
            if (!countField.isNull()) {
                dictCount = dictPtr.add(api.field_get_offset(countField)).readU32();
            }
        } catch (e) {}
        const result = {};
        const ENTRY_SIZE = 24; // hashCode(4) + next(4) + key(8) + value(8)
        const dataStart = 32;  // after klass(8)+monitor(8)+bounds(8)+max_length(8)
        // Find first occupied entry to validate (don't assume index 0 is used)
        let validIdx = -1;
        for (let i = 0; i < Math.min(maxLen, 20); i++) {
            try {
                const e = entriesArr.add(dataStart + i * ENTRY_SIZE);
                const keyPtr = e.add(8).readPointer();
                if (keyPtr.isNull()) continue;
                const ks = readIl2cppString(keyPtr);
                if (ks && !ks.startsWith('(') && ks.length > 0 && ks.length < 200) {
                    validIdx = i;
                    break;
                }
            } catch (e) { continue; }
        }
        if (validIdx < 0) return `(no valid entries found, maxLen=${maxLen})`;
        // Enumerate all slots, skip empty (null key)
        for (let i = 0; i < maxLen; i++) {
            try {
                const e = entriesArr.add(dataStart + i * ENTRY_SIZE);
                const keyPtr = e.add(8).readPointer();
                if (keyPtr.isNull()) continue;
                const k = readIl2cppString(keyPtr);
                if (!k || k.startsWith('(')) continue;
                const valPtr = e.add(16).readPointer();
                const v = valPtr.isNull() ? '(null)' : readIl2cppString(valPtr);
                result[k] = v;
            } catch (e) { continue; }
        }
        return result;
    } catch (e) {
        return `(dict error: ${e.message})`;
    }
}
function findMethodImpl(className, methodName, paramCount) {
    const domain = api.domain_get();
    const countPtr = Memory.alloc(Process.pointerSize);
    const assemblies = api.domain_get_assemblies(domain, countPtr);
    const count = countPtr.readU32();

    let image = ptr(0);
    const emptyNs = Memory.allocUtf8String('');
    for (let i = 0; i < count; i++) {
        const asm = assemblies.add(i * Process.pointerSize).readPointer();
        const img = api.assembly_get_image(asm);
        const name = api.image_get_name(img).readCString();
        if (name === 'Assembly-CSharp' || name === 'Assembly-CSharp.dll') { image = img; break; }
    }
    if (image.isNull()) {
        console.log('[!] Assembly-CSharp not found');
        return ptr(0);
    }

    const klass = api.class_from_name(image, emptyNs, Memory.allocUtf8String(className));
    if (klass.isNull()) {
        console.log(`[!] Class not found: ${className}`);
        return ptr(0);
    }

    const iter = Memory.alloc(Process.pointerSize);
    iter.writePointer(ptr(0));
    const candidates = [];
    while (true) {
        const method = api.class_get_methods(klass, iter);
        if (method.isNull()) break;
        const mName = api.method_get_name(method).readCString();
        if (mName !== methodName) continue;
        const pCount = api.method_get_param_count(method);
        // Get parameter type names
        const typeNames = [];
        for (let pi = 0; pi < pCount; pi++) {
            try {
                const t = api.method_get_param(method, pi);
                const tn = api.type_get_name(t).readCString();
                typeNames.push(tn);
            } catch (e) {
                typeNames.push('?');
            }
        }
        console.log(`[?] ${className}.${methodName} overload: (${typeNames.join(', ')}) @ ${method.readPointer()}`);
        if (pCount === paramCount) {
            let retName = '?';
            try { retName = api.type_get_name(api.method_get_return_type(method)).readCString(); } catch (e) {}
            candidates.push({ method, typeNames, fnPtr: method.readPointer(), retName });
        }
    }
    if (candidates.length === 0) {
        console.log(`[!] Method not found: ${className}.${methodName} (${paramCount} params)`);
        return null;
    }
    // Prefer the overload where all params are System.String
    for (const c of candidates) {
        if (c.typeNames.every(t => t === 'System.String')) {
            console.log(`[+] Found ${className}.${methodName}(${c.typeNames.join(', ')}) -> ${c.retName} @ ${c.fnPtr}`);
            return c;
        }
    }
    // Fallback: first candidate
    const c = candidates[0];
    console.log(`[+] Found ${className}.${methodName}(${c.typeNames.join(', ')}) -> ${c.retName} @ ${c.fnPtr} (first match)`);
    return c;
}

// Safely describe a return value: klass name + raw bytes, no string assumption
function describeRetval(rv) {
    try {
        if (rv === null || rv === undefined) return '(null/undefined)';
        // Value-type return (int, bool, etc.) comes as a JS number, not a pointer
        if (typeof rv === 'number') return `(number: ${rv} / 0x${rv.toString(16)})`;
        if (typeof rv !== 'object' || typeof rv.isNull !== 'function')
            return `(${typeof rv}: ${String(rv).substring(0, 100)})`;
        if (rv.isNull()) return '(null pointer)';
        const klass = api.object_get_class(rv);
        if (klass.isNull()) return `(no klass @ ${rv})`;
        const kname = api.class_get_name(klass).readCString();
        let hex = '';
        try {
            for (let i = 0; i < 32; i++) hex += rv.add(i).readU8().toString(16).padStart(2, '0') + ' ';
        } catch (e) { hex = 'unreadable'; }
        let asStr = '';
        if (kname === 'String') {
            asStr = ` str="${trunc(readIl2cppString(rv), 200)}"`;
        }
        return `klass=${kname} @ ${rv} hex=[${hex}]${asStr}`;
    } catch (e) {
        return `(describe failed: ${e.message})`;
    }
}

// Find a method in any loaded assembly (for System.Convert etc.)
function findMethodAnywhere(className, methodName, paramCount) {
    const domain = api.domain_get();
    const countPtr = Memory.alloc(Process.pointerSize);
    const assemblies = api.domain_get_assemblies(domain, countPtr);
    const count = countPtr.readU32();
    const dot = className.lastIndexOf('.');
    const namespaceName = dot >= 0 ? className.substring(0, dot) : '';
    const shortClassName = dot >= 0 ? className.substring(dot + 1) : className;
    const nsPtr = Memory.allocUtf8String(namespaceName);
    const classPtr = Memory.allocUtf8String(shortClassName);
    for (let i = 0; i < count; i++) {
        try {
            const asm = assemblies.add(i * Process.pointerSize).readPointer();
            const img = api.assembly_get_image(asm);
            const klass = api.class_from_name(img, nsPtr, classPtr);
            if (klass.isNull()) continue;
            const iter = Memory.alloc(Process.pointerSize);
            iter.writePointer(ptr(0));
            while (true) {
                const method = api.class_get_methods(klass, iter);
                if (method.isNull()) break;
                if (api.method_get_name(method).readCString() !== methodName) continue;
                if (api.method_get_param_count(method) !== paramCount) continue;
                return method.readPointer();
            }
        } catch (e) { continue; }
    }
    return ptr(0);
}

function findMethodAnywhereTyped(className, methodName, paramCount, preferredSecondType) {
    const domain = api.domain_get();
    const countPtr = Memory.alloc(Process.pointerSize);
    const assemblies = api.domain_get_assemblies(domain, countPtr);
    const count = countPtr.readU32();
    const dot = className.lastIndexOf('.');
    const namespaceName = dot >= 0 ? className.substring(0, dot) : '';
    const shortClassName = dot >= 0 ? className.substring(dot + 1) : className;
    const nsPtr = Memory.allocUtf8String(namespaceName);
    const classPtr = Memory.allocUtf8String(shortClassName);
    for (let i = 0; i < count; i++) {
        try {
            const asm = assemblies.add(i * Process.pointerSize).readPointer();
            const img = api.assembly_get_image(asm);
            const klass = api.class_from_name(img, nsPtr, classPtr);
            if (klass.isNull()) continue;
            const iter = Memory.alloc(Process.pointerSize);
            iter.writePointer(ptr(0));
            while (true) {
                const method = api.class_get_methods(klass, iter);
                if (method.isNull()) break;
                if (api.method_get_name(method).readCString() !== methodName) continue;
                if (api.method_get_param_count(method) !== paramCount) continue;
                const typeNames = [];
                for (let pi = 0; pi < paramCount; pi++) {
                    try { typeNames.push(api.type_get_name(api.method_get_param(method, pi)).readCString()); }
                    catch (e) { typeNames.push('?'); }
                }
                let retName = '?';
                try { retName = api.type_get_name(api.method_get_return_type(method)).readCString(); } catch (e) {}
                console.log('[?] ' + className + '.' + methodName + ' overload: (' + typeNames.join(', ') + ') -> ' + retName + ' @ ' + method.readPointer());
                if (!preferredSecondType || typeNames[1] === preferredSecondType ||
                    (preferredSecondType === 'System.Object[]' && typeNames[1].indexOf('System.Object[]') >= 0)) {
                    return { fnPtr: method.readPointer(), typeNames: typeNames, retName: retName };
                }
            }
        } catch (e) { continue; }
    }
    return null;
}

function waitForIl2cpp() {
    return new Promise((resolve) => {
        const timer = setInterval(() => {
            try {
                const mod = findModuleBase(LIB_NAME);
                if (!mod) return; // not loaded yet
                initApi();
                const domain = api.domain_get();
                if (!domain.isNull()) {
                    clearInterval(timer);
                    resolve();
                } else {
                    console.log('[*] libil2cpp loaded, waiting for domain...');
                }
            } catch (e) {
                console.log(`[*] waiting for il2cpp... (${e.message})`);
            }
        }, 2000);
    });
}

function waitForAssembly() {
    return new Promise((resolve) => {
        console.log('[*] Waiting for Assembly-CSharp (enter the game world on the phone)...');
        let listed = false;
        const timer = setInterval(() => {
            try {
                const domain = api.domain_get();
                const countPtr = Memory.alloc(Process.pointerSize);
                const assemblies = api.domain_get_assemblies(domain, countPtr);
                const count = countPtr.readU32();
                let found = false;
                const names = [];
                for (let i = 0; i < count; i++) {
                    const asm = assemblies.add(i * Process.pointerSize).readPointer();
                    const img = api.assembly_get_image(asm);
                    const name = api.image_get_name(img).readCString();
                    names.push(name);
                    if (name === 'Assembly-CSharp' || name === 'Assembly-CSharp.dll') {
                        found = true;
                    }
                }
                if (found) {
                    clearInterval(timer);
                    console.log(`[*] Assembly-CSharp found (${count} assemblies loaded).`);
                    resolve();
                    return;
                }
                if (!listed && count > 5) {
                    listed = true;
                    console.log(`[*] Loaded assemblies (${count}): ${names.join(', ')}`);
                }
            } catch (e) {
                console.log(`[*] waiting for assembly... (${e.message})`);
            }
        }, 3000);
    });
}

// ---------- hooks ----------

async function main() {
    console.log('[*] justice_hook v4.3 starting...');
    await waitForIl2cpp();
    console.log('[*] IL2CPP domain ready.');
    await waitForAssembly();
    console.log('[*] Installing hooks...\n');

    let hookCount = 0;

    // V4_POST_Login (static, 3 params)
    try {
        const v4Login = findMethodImpl(CLASS_NAME, 'V4_POST_Login', 3);
        if (v4Login) {
            Interceptor.attach(v4Login.fnPtr, {
                onEnter(args) {
                    console.log('\n========== V4_POST_Login called ==========');
                    const names = PARAMS['V4_POST_Login'];
                    for (let i = 0; i < 3; i++) {
                        console.log(`  ${names[i]}: ${trunc(readIl2cppString(args[i]))}`);
                    }
                    this.callTime = Date.now();
                },
                onLeave(retval) {
                    console.log(`  [return after ${Date.now() - this.callTime}ms]`);
                    console.log('========================================\n');
                }
            });
            hookCount++;
        }
    } catch (e) { console.log(`[!] V4_POST_Login hook failed: ${e.message}`); }

    // Sign (static, 2 params) — THE MOST IMPORTANT ONE
    // Actual signature: Sign(System.String, Dictionary<String,String>)
    const signThreads = new Set();
    try {
        const sign = findMethodImpl(CLASS_NAME, 'Sign', 2);
        if (sign) {
            console.log(`[*] Sign return type: ${sign.retName}`);
            Interceptor.attach(sign.fnPtr, {
                onEnter(args) {
                    signThreads.add(Process.getCurrentThreadId());
                    console.log('\n---------- Sign called ----------');
                    const contentVal = readIl2cppString(args[0]);
                    this.inputs = { content: contentVal };
                    this.dictPtr = args[1];  // store for onLeave re-read
                    console.log(`  content: ${trunc(contentVal)}`);
                    const dictVal = readDictionary(args[1]);
                    this.inputs.dict = dictVal;
                    console.log(`  dict: ${JSON.stringify(dictVal)}`);
                    this.startTime = Date.now();
                },
                onLeave(retval) {
                    signThreads.delete(Process.getCurrentThreadId());
                    const elapsed = Date.now() - this.startTime;
                    // Sign returns void - check if dict was modified in-place
                    let afterDict = '';
                    try {
                        // args[1] not available in onLeave, use stored pointer
                        afterDict = JSON.stringify(readDictionary(this.dictPtr));
                    } catch (e) { afterDict = `(re-read failed: ${e.message})`; }
                    console.log(`  => SIGN OUTPUT: void (dict modified in-place?)`);
                    console.log(`  => dict after: ${afterDict}`);
                    console.log(`  (${elapsed}ms)`);
                    console.log('----------------------------------\n');
                    console.log(`[SIGN_DATA] input_content=${JSON.stringify(trunc(this.inputs.content, 2000))} input_dict=${JSON.stringify(this.inputs.dict)} dict_after=${afterDict}`);
                }
            });
            hookCount++;
        }
    } catch (e) { console.log(`[!] Sign hook failed: ${e.message}`); }

    // GetDefaultParams (static, 0 params) — returns Dictionary<string,string>
    try {
        const getDefault = findMethodImpl(CLASS_NAME, 'GetDefaultParams', 0);
        if (getDefault) {
            Interceptor.attach(getDefault.fnPtr, {
                onEnter(args) {
                    console.log('\n---------- GetDefaultParams called ----------');
                },
                onLeave(retval) {
                    const dict = readDictionary(retval);
                    console.log(`  [return] ${JSON.stringify(dict)}`);
                    console.log('----------------------------------\n');
                }
            });
            hookCount++;
        }
    } catch (e) { console.log(`[!] GetDefaultParams hook failed: ${e.message}`); }

    // V3_POST_AllInOne (static, 1 param)
    try {
        const allInOne = findMethodImpl(CLASS_NAME, 'V3_POST_AllInOne', 1);
        if (allInOne) {
            Interceptor.attach(allInOne.fnPtr, {
                onEnter(args) {
                    console.log('\n========== V3_POST_AllInOne called ==========');
                    console.log(`  app_key: ${trunc(readIl2cppString(args[0]))}`);
                },
                onLeave(retval) {
                    console.log('============================================\n');
                }
            });
            hookCount++;
        }
    } catch (e) { console.log(`[!] V3_POST_AllInOne hook failed: ${e.message}`); }

    // System.String.Join(string, object[]) — Sign이 MD5에 넘기는 원문 추적용
    try {
        const join = findMethodAnywhereTyped('System.String', 'Join', 2, 'System.Object[]');
        if (join) {
            console.log('[+] Hooking System.String.Join(' + join.typeNames.join(', ') + ') @ ' + join.fnPtr);
            Interceptor.attach(join.fnPtr, {
                onEnter(args) {
                    if (!signThreads.has(Process.getCurrentThreadId())) return;
                    this.inSign = true;
                    const separator = readIl2cppString(args[0]);
                    const values = readIl2cppArrayStrings(args[1], 100);
                    console.log('\n[JOIN_DATA] String.Join called inside Sign');
                    console.log('  separator: ' + JSON.stringify(separator));
                    console.log('  count: ' + values.length);
                    for (let i = 0; i < values.length; i++) console.log('  value[' + i + ']: ' + JSON.stringify(trunc(values[i], 2000)));
                    console.log('  joined_preview: ' + JSON.stringify(trunc(values.join(separator), 10000)));
                },
                onLeave(retval) {
                    if (!this.inSign) return;
                    console.log('  joined_actual: ' + JSON.stringify(trunc(readIl2cppString(retval), 10000)));
                    console.log('  [JOIN_DATA END]');
                }
            });
            hookCount++;
        } else console.log('[!] System.String.Join(string, object[]) not found');
    } catch (e) { console.log('[!] String.Join hook failed: ' + e.message); }

    // AliothEngine.Encrypt.MD5HashString(string) — Sign 최종 입력/출력 확인
    try {
        const md5 = findMethodAnywhereTyped('AliothEngine.Encrypt', 'MD5HashString', 1, null);
        if (md5) {
            console.log('[+] Hooking AliothEngine.Encrypt.MD5HashString(' + md5.typeNames.join(', ') + ') @ ' + md5.fnPtr);
            Interceptor.attach(md5.fnPtr, {
                onEnter(args) {
                    if (!signThreads.has(Process.getCurrentThreadId())) return;
                    this.inSign = true;
                    this.input = readIl2cppString(args[0]);
                    console.log('[MD5_DATA] input: ' + JSON.stringify(trunc(this.input, 10000)));
                },
                onLeave(retval) {
                    if (!this.inSign) return;
                    console.log('[MD5_DATA] output: ' + JSON.stringify(readIl2cppString(retval)));
                }
            });
            hookCount++;
        } else console.log('[!] AliothEngine.Encrypt.MD5HashString not found');
    } catch (e) { console.log('[!] MD5HashString hook failed: ' + e.message); }

    // System.Convert.ToBase64String(byte[]) — t 생성 추적용
    try {
        const b64 = findMethodAnywhere('System.Convert', 'ToBase64String', 1);
        if (!b64.isNull()) {
            console.log(`[+] Hooking System.Convert.ToBase64String @ ${b64}`);
            Interceptor.attach(b64, {
                onEnter(args) {
                    try {
                        const arr = args[0];
                        if (!arr.isNull()) {
                            const len = arr.add(24).readU32();
                            let hex = '';
                            const n = Math.min(len, 16);
                            for (let i = 0; i < n; i++)
                                hex += arr.add(32 + i).readU8().toString(16).padStart(2, '0');
                            console.log(`[B64] ToBase64String input: len=${len} head=[${hex}]`);
                            this.inLen = len;
                        }
                    } catch (e) {}
                },
                onLeave(retval) {
                    try {
                        const s = readIl2cppString(retval);
                        if (s && s.length > 100)
                            console.log(`[B64] => output len=${s.length} head=${s.substring(0, 40)}...`);
                    } catch (e) {}
                }
            });
            hookCount++;
        } else {
            console.log('[!] System.Convert.ToBase64String not found');
        }
    } catch (e) { console.log(`[!] ToBase64String hook failed: ${e.message}`); }

    console.log(`\n[*] ${hookCount} hooks installed. Trigger a login in the game...`);
    console.log('[*] Look for [SIGN_DATA], [JOIN_DATA], [MD5_DATA] and [B64] lines.\n');
}

main();
