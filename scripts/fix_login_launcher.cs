// Fix Tribe Login.exe: the double-click launcher for scripts/fix_login.sh, the one-step fix (the re-seed) for when
// Go Live stops working on the modded Tribe. It opens a console window, runs the script in Git Bash from the project
// folder and keeps the window open at the end.
// Rebuild (Git Bash, from the project folder; csc wants backslashes in these paths):
//   MSYS_NO_PATHCONV=1 /c/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe -nologo -target:exe \
//       '-win32icon:scripts\fix_login.ico' '-out:..\Fix Tribe Login.exe' 'scripts\fix_login_launcher.cs'
using System;
using System.Diagnostics;
using System.IO;

class FixTribeLogin
{
    static int Main(string[] args)
    {
        Console.Title = "Fix Tribe Login";
        Console.CancelKeyPress += (s, e) => { e.Cancel = true; };   // Ctrl-C stops the script, not this window

        string exeDir = AppDomain.CurrentDomain.BaseDirectory;
        string[] repos = { Path.Combine(exeDir, "tribe hack"), @"C:\Users\Chris\OneDrive\Desktop\tribe hack" };
        string repo = null;
        foreach (string r in repos)
            if (File.Exists(Path.Combine(r, @"scripts\fix_login.sh"))) { repo = r; break; }

        string[] bashes = {
            @"C:\Program Files\Git\bin\bash.exe",
            @"C:\Program Files (x86)\Git\bin\bash.exe",
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), @"Programs\Git\bin\bash.exe"),
        };
        string bash = null;
        foreach (string b in bashes)
            if (File.Exists(b)) { bash = b; break; }

        int code = 1;
        if (repo == null)
            Console.WriteLine("Can't find \"tribe hack\\scripts\\fix_login.sh\" (looked next to this file and on the Desktop).");
        else if (bash == null)
            Console.WriteLine("Can't find Git Bash (C:\\Program Files\\Git\\bin\\bash.exe): install Git for Windows.");
        else
        {
            string a = "scripts/fix_login.sh";
            foreach (string x in args) a += " \"" + x + "\"";
            ProcessStartInfo psi = new ProcessStartInfo(bash, a);
            psi.WorkingDirectory = repo;
            psi.UseShellExecute = false;                              // same window: the script's questions come here
            try { Process p = Process.Start(psi); p.WaitForExit(); code = p.ExitCode; }
            catch (Exception e) { Console.WriteLine("Couldn't start Git Bash: " + e.Message); }
        }
        Console.WriteLine();
        Console.Write("Press Enter to close this window...");
        Console.ReadLine();
        return code;
    }
}
