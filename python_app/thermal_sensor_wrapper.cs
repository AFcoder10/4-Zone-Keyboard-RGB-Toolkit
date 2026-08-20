using System;
using System.Diagnostics;
using System.Reflection;

[assembly: AssemblyTitle("thermal_sensor_access_v3")]
[assembly: AssemblyDescription("Temperature Monitor Background Service")]
[assembly: AssemblyProduct("4-Zone RGB Toolkit")]

class Program {
    static void Main(string[] args) {
        if (args.Length < 2) return;
        string py = args[0];
        string script = args[1];
        System.Text.StringBuilder sb = new System.Text.StringBuilder();
        sb.Append("\"").Append(script).Append("\"");
        for(int i=2; i<args.Length; i++) {
            sb.Append(" \"").Append(args[i].Replace("\"", "\\\"")).Append("\"");
        }
        string allArgs = sb.ToString();
        
        ProcessStartInfo info = new ProcessStartInfo();
        info.FileName = py;
        info.Arguments = allArgs;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        
        using (Process p = Process.Start(info))
        {
        }
    }
}
