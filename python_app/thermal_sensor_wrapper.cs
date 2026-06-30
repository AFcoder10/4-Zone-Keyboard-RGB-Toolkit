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
        string allArgs = "\"" + script + "\"";
        for(int i=2; i<args.Length; i++) {
            allArgs += " " + args[i];
        }
        
        ProcessStartInfo info = new ProcessStartInfo();
        info.FileName = py;
        info.Arguments = allArgs;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        
        Process.Start(info);
    }
}
