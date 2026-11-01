// mesh_export: export Tribe's cooked meshes and textures (Android, ASTC) to glTF + PNG with CUE4Parse, from the loose
// files `repak unpack` wrote and the hook's usmap in version 3 (`uasset_tool downgrade`: CUE4Parse 1.2.2 for .NET 8
// reads no later version).
//   mesh_export <dir holding Content/ (…/all/TribeXR)> <file_v3.usmap> <out dir> [options] <path | folder/> ...
//   e.g. mesh_export D:/TribeUE/tribe_assets/all/TribeXR pulled/TribeXR_full_v3.usmap D:/TribeUE/tribe_models
//            --meshes TribeXR/Content/Equipment/Models/SkeletalMeshes/
// A folder (trailing /, searched recursively) exports every matching object in it. Options (apply to the targets
// after them): --meshes (StaticMesh + SkeletalMesh only), --textures (Texture2D only, decoded straight to PNG), --all
// (both, the default), --no-materials (meshes without their materials' textures: control meshes share their model's
// big atlases, and re-decoding those per mesh is what makes a full run slow), --materials. Existing PNGs are skipped.
// Prints one line per object: OK <type> <path> -> <file>, SKIP, or FAIL.
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.SkeletalMesh;
using CUE4Parse.UE4.Assets.Exports.StaticMesh;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion;
using CUE4Parse_Conversion.Meshes;
using CUE4Parse_Conversion.Textures;

if (args.Length < 4) { Console.Error.WriteLine("usage: mesh_export <root> <usmap v3> <outdir> [--meshes|--textures|--all] [--no-materials|--materials] <path|folder/> ..."); return 2; }
var provider = new DefaultFileProvider(args[0], SearchOption.AllDirectories, true, new VersionContainer(EGame.GAME_UE5_4));
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(args[1]);
provider.Initialize();
Console.WriteLine($"{provider.Files.Count} files, project {provider.ProjectName}");
var outDir = new DirectoryInfo(args[2]); outDir.Create();
bool meshes = true, textures = true, materials = true;
int ok = 0, fail = 0, skip = 0;

void ExportMesh(UObject o, string path)
{
    try
    {
        var ex = new Exporter(o, new ExporterOptions { LodFormat = ELodFormat.FirstLod, MeshFormat = EMeshFormat.Gltf2, TextureFormat = ETextureFormat.Png, ExportMaterials = materials });
        if (ex.TryWriteToDir(outDir, out _, out var saved)) { ok++; Console.WriteLine($"OK {o.ExportType} {path} -> {saved}"); }
        else { fail++; Console.WriteLine($"FAIL {o.ExportType} {path}: exporter wrote nothing"); }
    }
    catch (Exception e) { fail++; Console.WriteLine($"FAIL {o.ExportType} {path}: {e.GetType().Name}: {e.Message.Split('\n')[0]}"); }
}
void ExportTexture(UTexture2D t, string pkg)
{
    var file = Path.Combine(outDir.FullName, Path.ChangeExtension(pkg, ".png"));
    if (File.Exists(file)) { skip++; return; }
    try
    {
        using var bmp = t.Decode(ETexturePlatform.DesktopMobile);
        if (bmp == null) { fail++; Console.WriteLine($"FAIL Texture2D {pkg}: no decodable mip"); return; }
        using var data = bmp.Encode(ETextureFormat.Png, 100);
        Directory.CreateDirectory(Path.GetDirectoryName(file));
        File.WriteAllBytes(file, data.ToArray());
        ok++; Console.WriteLine($"OK Texture2D {pkg} -> {file} ({bmp.Width}x{bmp.Height})");
    }
    catch (Exception e) { fail++; Console.WriteLine($"FAIL Texture2D {pkg}: {e.GetType().Name}: {e.Message.Split('\n')[0]}"); }
}
foreach (var target in args.Skip(3))
{
    switch (target)
    {
        case "--meshes": meshes = true; textures = false; continue;
        case "--textures": meshes = false; textures = true; continue;
        case "--all": meshes = textures = true; continue;
        case "--no-materials": materials = false; continue;
        case "--materials": materials = true; continue;
    }
    var pkgs = target.EndsWith('/')
        ? provider.Files.Keys.Where(k => k.StartsWith(target, StringComparison.OrdinalIgnoreCase) && k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase)).OrderBy(k => k).ToList()
        : new List<string> { target.EndsWith(".uasset") ? target : target + ".uasset" };
    foreach (var pk in pkgs)
    {
        try
        {
            var pkg = provider.LoadPackage(pk);
            foreach (var lazy in pkg.ExportsLazy)
            {
                var o = lazy.Value;
                if (meshes && (o is UStaticMesh || o is USkeletalMesh)) ExportMesh(o, pk);
                else if (textures && o is UTexture2D t) ExportTexture(t, pk);
            }
        }
        catch (Exception e) { fail++; Console.WriteLine($"FAIL package {pk}: {e.GetType().Name}: {e.Message.Split('\n')[0]}"); }
    }
}
Console.WriteLine($"exported {ok}, skipped {skip} (already there), failed {fail}");
return fail > 0 && ok == 0 ? 1 : 0;
