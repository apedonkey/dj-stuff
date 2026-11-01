// uasset_tool: read Tribe's cooked assets offline with UAssetAPI 1.1.0 and the TribeXR.usmap that hook/usmap.cpp writes.
//   usmap <file.usmap> [Struct|Enum ...]          counts, then each named schema or enum
//   asset <file.usmap|-> <file.uasset> [out.json] exports by type, how many stayed raw (unparsed), functions with decoded
//                                                 bytecode; optionally the whole asset as JSON. "-" = no mappings (what
//                                                 Tribe's assets gave before TribeXR.usmap: every export raw)
//   inventory <file.usmap> <dir> <out.tsv>        every .uasset/.umap under dir: its main class, parent, raw exports, functions
//   augment <file.usmap> <dir> <out.usmap>        adds the Blueprint classes, user structs and user enums defined in the
//                                                 assets under dir that the runtime dump lacks (classes that weren't
//                                                 loaded when it ran), from their own ClassExports: then a Blueprint
//                                                 whose Blueprint parent wasn't loaded parses fully too
//   downgrade <in.usmap> <out.usmap>              the same mappings as version 3 (CUE4Parse 1.2.2 for .NET 8 reads
//                                                 no later): each enum's names placed at the index of their value
//   dump <file.usmap> <dir> <outdir>              per Blueprint/struct/enum/data table/skeleton/skeletal mesh/level: imports, exports with their
//                                                 property data, struct and class property lists, and every function's
//                                                 bytecode through UAssetAPI's KismetSerializer (statement offsets,
//                                                 resolved names), as <outdir>/<path under Content>.json
using Newtonsoft.Json.Linq;
using UAssetAPI;
using UAssetAPI.ExportTypes;
using UAssetAPI.FieldTypes;
using UAssetAPI.Kismet;
using UAssetAPI.Unversioned;
using UAssetAPI.UnrealTypes;

static string T(UsmapPropertyData d) => d switch
{
    null => "?",
    UsmapEnumData e => $"Enum({T(e.InnerType)},{e.Name})",
    UsmapStructData s => $"Struct({s.StructType})",
    UsmapMapData m => $"Map<{T(m.InnerType)},{T(m.ValueType)}>",
    UsmapArrayData a => $"{a.Type.ToString().Replace("Property", "")}<{T(a.InnerType)}>",
    _ => d.Type.ToString().Replace("Property", ""),
};
static IEnumerable<string> Assets(string dir) =>                       // packages: .uasset, and .umap (levels and their level Blueprints)
    Directory.EnumerateFiles(dir, "*.*", SearchOption.AllDirectories)
        .Where(p => p.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase) || p.EndsWith(".umap", StringComparison.OrdinalIgnoreCase))
        .OrderBy(p => p, StringComparer.Ordinal);
static UAsset Load(string path, Usmap map) => new UAsset(path, EngineVersion.VER_UE5_4, map);

if (args.Length >= 2 && args[0] == "usmap")
{
    var u = new Usmap(args[1]);
    Console.WriteLine($"version={u.Version} names={u.NameMap.Count} enums={u.EnumMap.Count} schemas={u.Schemas.Count}");
    foreach (var q in args.Skip(2))
    {
        if (u.EnumMap.TryGetValue(q, out var e))
            Console.WriteLine($"enum {e.Name}:" + string.Concat(e.Values.OrderBy(k => k.Key).Select(k => $" {k.Key}={k.Value}")));
        else if (u.Schemas.TryGetValue(q, out var s))
        {
            Console.WriteLine($"struct {s.Name} : {s.SuperType ?? "-"} slots={s.PropCount}");
            foreach (var kv in s.Properties.OrderBy(k => k.Key))
                Console.WriteLine($"  {kv.Key} {kv.Value.Name}[{kv.Value.ArrayIndex}/{kv.Value.ArraySize}] {T(kv.Value.PropertyData)}");
        }
        else Console.WriteLine($"{q}: not found");
    }
    return 0;
}
if (args.Length >= 3 && args[0] == "asset")
{
    var a = Load(args[2], args[1] == "-" ? null : new Usmap(args[1]));
    Console.WriteLine($"{Path.GetFileName(args[2])}: {a.Exports.Count} exports, unversioned={a.HasUnversionedProperties}");
    foreach (var g in a.Exports.GroupBy(x => x.GetType().Name).OrderBy(g => g.Key))
        Console.WriteLine($"  {g.Key,-22} {g.Count()}");
    var funcs = a.Exports.OfType<FunctionExport>().ToList();
    Console.WriteLine($"raw (unparsed) exports: {a.Exports.Count(x => x is RawExport)}");
    Console.WriteLine($"functions: {funcs.Count}, with decoded bytecode: {funcs.Count(f => f.ScriptBytecode != null && f.ScriptBytecode.Length > 0)}");
    if (args.Length >= 4) { File.WriteAllText(args[3], a.SerializeJson(true)); Console.WriteLine($"wrote {args[3]}"); }
    return 0;
}
if (args.Length >= 4 && args[0] == "inventory")
{
    var map = new Usmap(args[1]);
    using var w = new StreamWriter(args[3]);
    w.WriteLine("asset\tclass\tparent\texports\traw\tfunctions\terror");
    foreach (var p in Assets(args[2]))
    {
        string rel = Ue.Rel(args[2], p);
        try
        {
            var a = Load(p, map);
            var main = Ue.MainExport(a);
            string parent = main is StructExport se ? Ue.Path(a, se.SuperStruct) : "";
            w.WriteLine($"{rel}\t{(main == null ? "?" : Ue.ClassOf(a, main))}\t{parent}\t{a.Exports.Count}\t{a.Exports.Count(x => x is RawExport)}\t{a.Exports.Count(x => x is FunctionExport)}\t");
        }
        catch (Exception ex) { w.WriteLine($"{rel}\t\t\t\t\t\t{ex.GetType().Name}: {ex.Message.Replace('\t', ' ').Replace('\n', ' ')}"); }
    }
    Console.WriteLine($"wrote {args[3]}");
    return 0;
}
if (args.Length >= 4 && args[0] == "augment")
{
    var m = UsmapModel.Read(args[1]);
    var map = new Usmap(args[1]);
    var haveS = new HashSet<string>(m.Structs.Select(s => s.Name)); var haveE = new HashSet<string>(m.Enums.Select(e => e.Name));
    int addS = 0, addE = 0, fail = 0; var supers = new HashSet<string>();
    foreach (var p in Assets(args[2]))
    {
        UAsset a; try { a = Load(p, map); } catch (Exception ex) { fail++; Console.Error.WriteLine($"  {Ue.Rel(args[2], p)}: {ex.Message}"); continue; }
        foreach (var e in a.Exports)
        {
            string name = e.ObjectName.ToString();
            if (e is EnumExport ee && ee.Enum?.Names != null && haveE.Add(name))
            {
                var ue = new UE { Name = name };
                foreach (var (n, v) in ee.Enum.Names) { string s = n.ToString(); int c = s.IndexOf("::", StringComparison.Ordinal); ue.Items.Add((v, c >= 0 ? s[(c + 2)..] : s)); }
                m.Enums.Add(ue); addE++;
            }
            else if (e is StructExport se && e is not FunctionExport && haveS.Add(name))
            {
                var us = new US { Name = name, Super = se.SuperStruct.IsNull() ? null : Ue.Name(a, se.SuperStruct) };
                foreach (var fp in se.LoadedProperties ?? Array.Empty<FProperty>())
                {
                    int dim = Math.Max(1, (int)fp.ArrayDim);
                    us.Props.Add(new UP { Slot = us.Slots, Dim = dim, Name = fp.Name.ToString(), T = UsmapModel.Conv(a, fp) });
                    us.Slots += dim;
                }
                m.Structs.Add(us); addS++;
                if (us.Super != null) supers.Add(us.Super);
            }
        }
    }
    var missing = supers.Where(s => !m.Structs.Any(x => x.Name == s)).OrderBy(s => s).ToList();
    m.Write(args[3]);
    Console.WriteLine($"added {addS} classes/structs and {addE} enums ({fail} assets unreadable); parents still missing: {missing.Count}");
    foreach (var s in missing) Console.WriteLine($"  missing parent: {s}");
    Console.WriteLine($"wrote {args[3]}: {m.Structs.Count} classes/structs, {m.Enums.Count} enums");
    return 0;
}
if (args.Length >= 4 && args[0] == "dump")
{
    var map = new Usmap(args[1]); int n = 0, bad = 0;
    foreach (var p in Assets(args[2]))
    {
        string rel = Ue.Rel(args[2], p);
        UAsset a; try { a = Load(p, map); } catch (Exception ex) { bad++; Console.Error.WriteLine($"  {rel}: {ex.Message}"); continue; }
        var main = Ue.MainExport(a); string cls = main == null ? "" : Ue.ClassOf(a, main);
        if (!(cls.EndsWith("BlueprintGeneratedClass") || cls is "UserDefinedStruct" or "UserDefinedEnum" or "DataTable" or "Skeleton" or "SkeletalMesh" or "World")) continue;
        var nameList = cls == "Skeleton" ? new JArray(a.GetNameMapIndexList().Select(s => s.ToString())) : null;
        KismetSerializer.asset = a;
        var root = new JObject { ["asset"] = rel, ["class"] = cls };
        var imps = new JArray();
        for (int i = 0; i < a.Imports.Count; i++)
            imps.Add(new JObject { ["i"] = -(i + 1), ["name"] = a.Imports[i].ObjectName.ToString(), ["class"] = a.Imports[i].ClassName.ToString(), ["path"] = Ue.Path(a, FPackageIndex.FromImport(i)) });
        root["imports"] = imps;
        var exps = new JArray();
        for (int i = 0; i < a.Exports.Count; i++)
        {
            var e = a.Exports[i];
            var jo = new JObject { ["i"] = i + 1, ["name"] = e.ObjectName.ToString(), ["class"] = Ue.ClassOf(a, e), ["type"] = e.GetType().Name, ["outer"] = e.OuterIndex.Index };
            if (e is RawExport) jo["raw"] = true;
            // a Skeleton's reference skeleton (bone names, parents, ref pose) is native data after its properties:
            // keep those bytes and the name list they index, for scripts/deck_catalog.py
            if (cls == "Skeleton" && e == main && e is NormalExport sk && sk.Extras != null) { jo["extras"] = Convert.ToBase64String(sk.Extras); jo["names"] = nameList; }
            if (e is NormalExport ne && ne.Data != null && ne.Data.Count > 0) jo["data"] = JToken.Parse(a.SerializeJsonObject(ne.Data));
            if (e is StructExport se)
            {
                jo["super"] = Ue.Path(a, se.SuperStruct);
                var props = new JArray();
                foreach (var fp in se.LoadedProperties ?? Array.Empty<FProperty>())
                    props.Add(new JObject { ["name"] = fp.Name.ToString(), ["type"] = Ue.TypeStr(a, fp), ["flags"] = (ulong)fp.PropertyFlags, ["dim"] = Math.Max(1, (int)fp.ArrayDim) });
                jo["props"] = props;
            }
            if (e is FunctionExport fe)
            {
                jo["fflags"] = fe.FunctionFlags.ToString();
                try { jo["code"] = KismetSerializer.SerializeScript(fe.ScriptBytecode ?? Array.Empty<UAssetAPI.Kismet.Bytecode.KismetExpression>()); }
                catch (Exception ex) { jo["codeError"] = ex.GetType().Name + ": " + ex.Message; }
            }
            if (e is EnumExport ee && ee.Enum?.Names != null)
                jo["enum"] = new JArray(ee.Enum.Names.Select(t => new JArray(t.Item1.ToString(), t.Item2)));
            if (e is DataTableExport dt && dt.Table?.Data != null) jo["rows"] = JToken.Parse(a.SerializeJsonObject(dt.Table.Data));
            exps.Add(jo);
        }
        root["exports"] = exps;
        string outp = Path.Combine(args[3], Path.ChangeExtension(rel, ".json"));
        Directory.CreateDirectory(Path.GetDirectoryName(outp));
        File.WriteAllText(outp, root.ToString(Newtonsoft.Json.Formatting.None));
        n++;
    }
    Console.WriteLine($"dumped {n} assets to {args[3]} ({bad} unreadable)");
    return 0;
}
if (args.Length >= 3 && args[0] == "downgrade")
{
    var m = UsmapModel.Read(args[1]); m.Write(args[2], 3);
    Console.WriteLine($"wrote {args[2]} as usmap version 3 (LargeEnums): {m.Structs.Count} classes/structs, {m.Enums.Count} enums, {m.Unordered} enums kept in their own order (values too big or negative)");
    return 0;
}
Console.Error.WriteLine("usage: uasset_tool usmap|asset|inventory|augment|dump|downgrade ... (see the header of Program.cs)");
return 2;

static class Ue
{
    public static string Rel(string root, string p) => System.IO.Path.GetRelativePath(root, p).Replace('\\', '/');
    public static string Name(UAsset a, FPackageIndex i) =>
        i.IsImport() ? i.ToImport(a).ObjectName.ToString() : i.IsExport() ? i.ToExport(a).ObjectName.ToString() : null;
    public static string Path(UAsset a, FPackageIndex i)              // "/Script/Engine.Actor", "/Game/X/BP_Y.BP_Y_C"
    {
        var parts = new List<string>(); var cur = i;
        for (int d = 0; d < 16 && !cur.IsNull(); d++)
        {
            if (cur.IsImport()) { var im = cur.ToImport(a); parts.Add(im.ObjectName.ToString()); cur = im.OuterIndex; }
            else { var ex = cur.ToExport(a); parts.Add(ex.ObjectName.ToString()); cur = ex.OuterIndex; }
        }
        if (parts.Count == 0) return "";
        parts.Reverse(); return parts[0] + (parts.Count > 1 ? "." + string.Join(":", parts.Skip(1)) : "");
    }
    public static string ClassOf(UAsset a, Export e) => e.ClassIndex.IsNull() ? "Class" : Name(a, e.ClassIndex);
    public static Export MainExport(UAsset a)                         // the package's own object (Blueprint class, struct ...)
    {
        string pkg = System.IO.Path.GetFileNameWithoutExtension(a.FilePath);
        return a.Exports.FirstOrDefault(x => x is ClassExport) ??
               a.Exports.FirstOrDefault(x => x.ObjectName.ToString() == pkg) ?? a.Exports.FirstOrDefault();
    }
    public static string TypeStr(UAsset a, FProperty p) => p switch
    {
        null => "?",
        FByteProperty b when !b.Enum.IsNull() => $"Enum({Name(a, b.Enum)})",
        FEnumProperty en => $"Enum({Name(a, en.Enum)})",
        FStructProperty s => $"Struct({Name(a, s.Struct)})",
        FArrayProperty ar => $"Array<{TypeStr(a, ar.Inner)}>",
        FSetProperty st => $"Set<{TypeStr(a, st.ElementProp)}>",
        FMapProperty mp => $"Map<{TypeStr(a, mp.KeyProp)},{TypeStr(a, mp.ValueProp)}>",
        FOptionalProperty op => $"Optional<{TypeStr(a, op.ValueProperty)}>",
        FClassProperty c => $"Class({Name(a, c.MetaClass)})",
        FSoftClassProperty sc => $"SoftClass({Name(a, sc.MetaClass)})",
        FObjectProperty o => $"{p.SerializedType.ToString().Replace("Property", "")}({Name(a, o.PropertyClass)})",
        FInterfaceProperty ip => $"Interface({Name(a, ip.InterfaceClass)})",
        _ => p.SerializedType.ToString().Replace("Property", ""),
    };
}

// the .usmap in memory, as hook/usmap_writer.h lays it out (version 4); read, add to, write back
sealed class UT { public byte K; public UT In, Val; public string S, E; }
sealed class UP { public int Slot, Dim; public string Name; public UT T; }
sealed class US { public string Name, Super; public int Slots; public List<UP> Props = new(); }
sealed class UE { public string Name; public List<(long v, string n)> Items = new(); }
sealed class UsmapModel
{
    public List<UE> Enums = new(); public List<US> Structs = new();
    static readonly Dictionary<string, byte> Kinds = new()
    {
        ["ByteProperty"] = 0, ["BoolProperty"] = 1, ["IntProperty"] = 2, ["FloatProperty"] = 3, ["ObjectProperty"] = 4,
        ["ObjectPtrProperty"] = 4, ["ClassProperty"] = 4, ["ClassPtrProperty"] = 4, ["NameProperty"] = 5, ["DelegateProperty"] = 6,
        ["DoubleProperty"] = 7, ["ArrayProperty"] = 8, ["StructProperty"] = 9, ["StrProperty"] = 10, ["TextProperty"] = 11,
        ["InterfaceProperty"] = 12, ["MulticastDelegateProperty"] = 13, ["MulticastInlineDelegateProperty"] = 13,
        ["MulticastSparseDelegateProperty"] = 13, ["WeakObjectProperty"] = 14, ["LazyObjectProperty"] = 15,
        ["SoftObjectProperty"] = 17, ["SoftClassProperty"] = 17, ["UInt64Property"] = 18, ["UInt32Property"] = 19,
        ["UInt16Property"] = 20, ["Int64Property"] = 21, ["Int16Property"] = 22, ["Int8Property"] = 23, ["MapProperty"] = 24,
        ["SetProperty"] = 25, ["EnumProperty"] = 26, ["FieldPathProperty"] = 27, ["OptionalProperty"] = 28,
        ["Utf8StrProperty"] = 29, ["AnsiStrProperty"] = 30,
    };
    public static UT Conv(UAsset a, FProperty p) => p switch
    {
        null => new UT { K = 0xFF },
        FByteProperty b when !b.Enum.IsNull() => new UT { K = 26, In = new UT { K = 0 }, E = Ue.Name(a, b.Enum) },
        FEnumProperty en => new UT { K = 26, In = Conv(a, en.UnderlyingProp), E = Ue.Name(a, en.Enum) },
        FStructProperty s => new UT { K = 9, S = Ue.Name(a, s.Struct) },
        FArrayProperty ar => new UT { K = 8, In = Conv(a, ar.Inner) },
        FSetProperty st => new UT { K = 25, In = Conv(a, st.ElementProp) },
        FMapProperty mp => new UT { K = 24, In = Conv(a, mp.KeyProp), Val = Conv(a, mp.ValueProp) },
        FOptionalProperty op => new UT { K = 28, In = Conv(a, op.ValueProperty) },
        _ => new UT { K = Kinds.TryGetValue(p.SerializedType.ToString(), out var k) ? k : (byte)0xFF },
    };
    public static UsmapModel Read(string path)
    {
        using var r = new BinaryReader(File.OpenRead(path));
        if (r.ReadUInt16() != 0x30C4) throw new InvalidDataException("not a .usmap");
        byte ver = r.ReadByte(); if (ver < 3 || ver > 4) throw new InvalidDataException($"usmap version {ver}: only 3 and 4");
        if (r.ReadInt32() != 0) throw new InvalidDataException("versioned usmap: not supported");
        if (r.ReadByte() != 0) throw new InvalidDataException("compressed usmap: not supported");
        r.ReadUInt32(); r.ReadUInt32();
        var names = new string[r.ReadUInt32()];
        for (int i = 0; i < names.Length; i++) names[i] = System.Text.Encoding.UTF8.GetString(r.ReadBytes(r.ReadUInt16()));
        string N() { int i = r.ReadInt32(); return i < 0 ? null : names[i]; }
        UT Ty() { var t = new UT { K = r.ReadByte() };
            switch (t.K) { case 26: t.In = Ty(); t.E = N(); break; case 9: t.S = N(); break;
                case 8: case 25: case 28: t.In = Ty(); break; case 24: t.In = Ty(); t.Val = Ty(); break; }
            return t; }
        var m = new UsmapModel();
        for (uint i = 0, n = r.ReadUInt32(); i < n; i++)
        {
            var e = new UE { Name = N() }; int c = r.ReadUInt16();
            for (int j = 0; j < c; j++) e.Items.Add(ver >= 4 ? (r.ReadInt64(), N()) : ((long)j, N()));
            m.Enums.Add(e);
        }
        for (uint i = 0, n = r.ReadUInt32(); i < n; i++)
        {
            var s = new US { Name = N(), Super = N() }; s.Slots = r.ReadUInt16(); int np = r.ReadUInt16();
            for (int j = 0; j < np; j++) s.Props.Add(new UP { Slot = r.ReadUInt16(), Dim = r.ReadByte(), Name = N(), T = Ty() });
            m.Structs.Add(s);
        }
        return m;
    }
    public int Unordered;                                    // v3 writes: enums kept in their own order (values too big or sparse)
    public void Write(string path, byte version = 4)
    {
        var idx = new Dictionary<string, int>(StringComparer.Ordinal); var names = new MemoryStream(); var nw = new BinaryWriter(names);
        int Nm(string s) { if (s == null) return -1; if (idx.TryGetValue(s, out var i)) return i; var b = System.Text.Encoding.UTF8.GetBytes(s);
            nw.Write((ushort)b.Length); nw.Write(b); idx[s] = idx.Count; return idx[s]; }
        var body = new MemoryStream(); var w = new BinaryWriter(body);
        void Ty(UT t) { w.Write(t.K);
            switch (t.K) { case 26: Ty(t.In); w.Write(Nm(t.E)); break; case 9: w.Write(Nm(t.S)); break;
                case 8: case 25: case 28: Ty(t.In); break; case 24: Ty(t.In); Ty(t.Val); break; } }
        w.Write((uint)Enums.Count);
        foreach (var e in Enums)
        {
            w.Write(Nm(e.Name));
            if (version >= 4) { w.Write((ushort)e.Items.Count); foreach (var (v, n) in e.Items) { w.Write(v); w.Write(Nm(n)); } continue; }
            // version 3 has no values: a reader takes entry i as value i. Lay the names out by value when they fit
            // (0 <= value < 4096, gaps named <Enum>_<value>); otherwise keep the order and count the enum as unordered.
            long max = e.Items.Count == 0 ? -1 : e.Items.Max(x => x.v);
            if (e.Items.Count > 0 && e.Items.All(x => x.v >= 0) && max < 4096)
            {
                var byVal = new Dictionary<long, string>(); foreach (var (v, n) in e.Items) byVal.TryAdd(v, n);
                w.Write((ushort)(max + 1)); for (long i = 0; i <= max; i++) w.Write(Nm(byVal.TryGetValue(i, out var n) ? n : $"{e.Name}_{i}"));
            }
            else { Unordered++; w.Write((ushort)e.Items.Count); foreach (var (_, n) in e.Items) w.Write(Nm(n)); }
        }
        w.Write((uint)Structs.Count);
        foreach (var s in Structs)
        {
            w.Write(Nm(s.Name)); w.Write(Nm(s.Super)); w.Write((ushort)Math.Min(s.Slots, 0xFFFF)); w.Write((ushort)s.Props.Count);
            foreach (var p in s.Props) { w.Write((ushort)p.Slot); w.Write((byte)Math.Min(p.Dim, 255)); w.Write(Nm(p.Name)); Ty(p.T); }
        }
        var payload = new MemoryStream(); var pw = new BinaryWriter(payload);
        pw.Write((uint)idx.Count); pw.Write(names.ToArray()); pw.Write(body.ToArray());
        using var f = new BinaryWriter(File.Create(path));
        f.Write((ushort)0x30C4); f.Write(version); f.Write(0); f.Write((byte)0);
        f.Write((uint)payload.Length); f.Write((uint)payload.Length); f.Write(payload.ToArray());
    }
}
