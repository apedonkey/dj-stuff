# Tiny Jython smoke test: confirm import worked and memory string search finds an anchor.
from ghidra.util.task import ConsoleTaskMonitor
mon = ConsoleTaskMonitor()
mem = currentProgram.getMemory()
print("SMOKE image_base=%s  min=%s  max=%s" % (
    currentProgram.getImageBase(), mem.getMinAddress(), mem.getMaxAddress()))
pat = bytes(bytearray("IsValidReadyPlayerMeAvatarUrl".encode("ascii")))
a = mem.findBytes(mem.getMinAddress(), pat, None, True, mon)
print("SMOKE found IsValidReadyPlayerMeAvatarUrl at: %s" % a)
print("SMOKE ok")
