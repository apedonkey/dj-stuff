# Add libhook.so as a DT_NEEDED dependency of libUnreal.so so the dynamic linker
# auto-loads (and runs the constructor of) libhook.so whenever libUnreal.so loads.
# This is a metadata edit (dynamic section), not a code patch.
import lief, sys

src, dst = sys.argv[1], sys.argv[2]
b = lief.parse(src)
needed = lambda o: [e.name for e in o.dynamic_entries if str(e.tag).endswith("NEEDED")]
before = needed(b)
if "libhook.so" not in before:
    b.add_library("libhook.so")
b.write(dst)

c = lief.parse(dst)
after = needed(c)
print("NEEDED before:", before)
print("NEEDED after :", after)
print("libhook.so present:", "libhook.so" in after)
print("entrypoint stable:", hex(b.entrypoint), "==", hex(c.entrypoint), b.entrypoint == c.entrypoint)
sys.exit(0 if "libhook.so" in after else 1)
