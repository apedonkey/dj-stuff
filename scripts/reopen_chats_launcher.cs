// Reopen Tribe Chats.exe: the double-click launcher that brings the project's Claude Code chats back after a restart.
// It reads scripts/chats.txt ("<tab name> | <chat id>" per line) and checks which of those chats are open right now
// (Claude Code's records in %USERPROFILE%\.claude\sessions: a pid and its process start time). It opens the closed ones
// in one new Windows Terminal window, a named tab each, running "claude --resume <id>" in the project folder.
// Typing S instead saves the chats open right now (the ones in the project folder) as the new list.
//   --dry-run         show what it would open and what S would save; opens nothing, writes nothing, no prompt
//   --test-terminal   open the same tabs, but each runs a 4-second echo instead of claude (checks the terminal command)
// Rebuild (Git Bash, from the project folder; csc wants backslashes in these paths):
//   MSYS_NO_PATHCONV=1 /c/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe -nologo -target:exe \
//       '-win32icon:scripts\reopen_chats.ico' '-out:..\Reopen Tribe Chats.exe' 'scripts\reopen_chats_launcher.cs'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

class ReopenTribeChats
{
    class Chat { public string Name, Id; }
    class Live { public string Id, Name, Cwd; }

    static readonly Regex ChatId = new Regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$");

    static string Field(string json, string key)          // a string or number field of a small one-level JSON record
    {
        Match m = Regex.Match(json, "\"" + key + "\"\\s*:\\s*(?:\"((?:[^\"\\\\]|\\\\.)*)\"|(-?[0-9]+))");
        if (!m.Success) return null;
        return m.Groups[1].Success ? Regex.Unescape(m.Groups[1].Value) : m.Groups[2].Value;
    }

    static List<Live> LiveChats(string home)               // the Claude Code chats running now
    {
        List<Live> list = new List<Live>();
        string dir = Path.Combine(home, @".claude\sessions");
        if (!Directory.Exists(dir)) return list;
        foreach (string f in Directory.GetFiles(dir, "*.json"))
        {
            string j;
            try { j = File.ReadAllText(f); } catch (Exception) { continue; }
            string id = Field(j, "sessionId"), pid = Field(j, "pid"), start = Field(j, "procStart");
            int p;
            if (id == null || !int.TryParse(pid, out p)) continue;
            try
            {
                Process pr = Process.GetProcessById(p);                // throws when no process has that pid
                long ft;
                if (start != null && long.TryParse(start, out ft) && Math.Abs(pr.StartTime.ToFileTimeUtc() - ft) > 20000000)
                    continue;                                          // a later process that got the same pid
            }
            catch (ArgumentException) { continue; }                    // not running
            catch (InvalidOperationException) { continue; }            // exited just now
            catch (Win32Exception) { }                                 // can't read its start time: count it as open
            list.Add(new Live { Id = id.ToLowerInvariant(), Name = Field(j, "name"), Cwd = Field(j, "cwd") });
        }
        return list;
    }

    static List<Chat> ReadList(string path, List<string> header)
    {
        List<Chat> chats = new List<Chat>();
        foreach (string raw in File.ReadAllLines(path))
        {
            string line = raw.Trim();
            if (line.StartsWith("#")) { header.Add(raw); continue; }
            if (line.Length == 0) continue;
            int bar = line.LastIndexOf('|');
            string id = bar < 0 ? "" : line.Substring(bar + 1).Trim().ToLowerInvariant();
            if (!ChatId.IsMatch(id)) { Console.WriteLine("  (skipped this line, no chat id after a '|': " + line + ")"); continue; }
            string name = line.Substring(0, bar).Trim().Replace(";", ",").Replace("\"", "'");   // ; and " would break the tab
            chats.Add(new Chat { Name = name.Length > 0 ? name : id.Substring(0, 8), Id = id });
        }
        return chats;
    }

    static string TerminalArgs(string repo, List<Chat> chats, bool test)
    {
        StringBuilder sb = new StringBuilder("-w new");
        for (int i = 0; i < chats.Count; i++)
        {
            string cmd = test ? "cmd /c echo Reopen Tribe Chats test: " + chats[i].Name + " & timeout /t 4 >nul"
                              : "cmd /k claude --resume " + chats[i].Id;
            sb.Append(i == 0 ? " " : " ; ");
            sb.Append("new-tab --title \"" + chats[i].Name + "\" --suppressApplicationTitle -d \"" + repo + "\" " + cmd);
        }
        return sb.ToString();
    }

    static bool Open(string repo, List<Chat> chats, bool test)
    {
        string wt = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), @"Microsoft\WindowsApps\wt.exe");
        try
        {
            if (File.Exists(wt))
            {
                ProcessStartInfo psi = new ProcessStartInfo(wt, TerminalArgs(repo, chats, test));
                psi.UseShellExecute = true;
                Process.Start(psi);
            }
            else                                                       // no Windows Terminal: a console window each
                foreach (Chat c in chats)
                {
                    ProcessStartInfo psi = new ProcessStartInfo("cmd.exe", test ? "/c echo test " + c.Name + " & timeout /t 4"
                                                                                : "/k title " + c.Name + " & claude --resume " + c.Id);
                    psi.WorkingDirectory = repo;
                    psi.UseShellExecute = true;
                    Process.Start(psi);
                }
            return true;
        }
        catch (Exception e) { Console.WriteLine("Couldn't open the terminal: " + e.Message); return false; }
    }

    static int Main(string[] args)
    {
        Console.Title = "Reopen Tribe Chats";
        bool dry = Array.IndexOf(args, "--dry-run") >= 0, test = Array.IndexOf(args, "--test-terminal") >= 0;
        int code = Run(dry, test);
        if (!dry && !test)
        {
            Console.WriteLine();
            Console.Write("Press Enter to close this window...");
            Console.ReadLine();
        }
        return code;
    }

    static int Run(bool dry, bool test)
    {
        string exeDir = AppDomain.CurrentDomain.BaseDirectory;
        string[] repos = { Path.Combine(exeDir, "tribe hack"), @"C:\Users\Chris\OneDrive\Desktop\tribe hack" };
        string repo = null;
        foreach (string r in repos)
            if (File.Exists(Path.Combine(r, @"scripts\chats.txt"))) { repo = Path.GetFullPath(r).TrimEnd('\\'); break; }
        if (repo == null) { Console.WriteLine("Can't find \"tribe hack\\scripts\\chats.txt\" (looked next to this file and on the Desktop)."); return 1; }
        string listPath = Path.Combine(repo, @"scripts\chats.txt");
        string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        string saved = Path.Combine(home, @".claude\projects\" + Regex.Replace(repo, "[^A-Za-z0-9]", "-"));   // the chats' history

        List<string> header = new List<string>();
        List<Chat> chats = ReadList(listPath, header);
        List<Live> live = LiveChats(home);
        HashSet<string> open = new HashSet<string>();
        foreach (Live l in live) open.Add(l.Id);

        Console.WriteLine("The saved chats (" + listPath + "):");
        List<Chat> toOpen = new List<Chat>();
        foreach (Chat c in chats)
        {
            string state;
            if (open.Contains(c.Id)) state = "open already";
            else if (!File.Exists(Path.Combine(saved, c.Id + ".jsonl"))) state = "NOT FOUND: no saved chat with this id";
            else { state = "closed, will reopen"; toOpen.Add(c); }
            Console.WriteLine("  " + c.Name.PadRight(30) + " " + state);
        }

        // what S saves: the chats open now in the project folder, the listed ones first (their names kept), then any others
        List<Chat> now = new List<Chat>();
        HashSet<string> here = new HashSet<string>();
        foreach (Live l in live)
            if (l.Cwd != null && string.Equals(l.Cwd.TrimEnd('\\'), repo, StringComparison.OrdinalIgnoreCase)) here.Add(l.Id);
        foreach (Chat c in chats) if (here.Contains(c.Id)) { now.Add(c); here.Remove(c.Id); }
        foreach (Live l in live)
            if (here.Contains(l.Id)) { now.Add(new Chat { Name = l.Name ?? l.Id.Substring(0, 8), Id = l.Id }); here.Remove(l.Id); }

        if (dry || test)
        {
            List<Chat> show = test ? chats : toOpen;
            Console.WriteLine();
            Console.WriteLine(show.Count == 0 ? "It would open nothing." : "It would run: wt " + TerminalArgs(repo, show, test));
            Console.WriteLine("S would save " + now.Count + " chats open now:");
            foreach (Chat c in now) Console.WriteLine("  " + c.Name + " | " + c.Id);
            if (test && show.Count > 0) { Console.WriteLine(); Console.WriteLine(Open(repo, show, true) ? "Test window opened." : "Test FAILED."); }
            return 0;
        }

        Console.WriteLine();
        if (toOpen.Count == 0) Console.WriteLine("Nothing to reopen: every saved chat is open already (or wasn't found).");
        Console.WriteLine("Press Enter to " + (toOpen.Count > 0 ? "reopen the " + toOpen.Count + " closed chat(s), one tab each" : "do nothing")
                          + ", or type S and Enter to save the " + now.Count + " chats open right now as the new list.");
        string ans = Console.ReadLine();
        if (ans != null && ans.Trim().Equals("S", StringComparison.OrdinalIgnoreCase))
        {
            List<string> lines = new List<string>(header);
            foreach (Chat c in now) lines.Add(c.Name + " | " + c.Id);
            File.WriteAllLines(listPath, lines.ToArray());
            Console.WriteLine("Saved " + now.Count + " chats. Rename a tab by editing its name in " + listPath + ".");
            return 0;
        }
        if (toOpen.Count == 0) return 0;
        if (!Open(repo, toOpen, false)) return 1;
        Console.WriteLine("Opened " + toOpen.Count + " chat(s) in a new Windows Terminal window.");
        return 0;
    }
}
