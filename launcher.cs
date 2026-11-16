using System;
using System.IO;
using System.Diagnostics;
using System.Net;
using System.Threading;
using System.Runtime.InteropServices;

namespace PeriquitoLauncher
{
    class Program
    {
        [DllImport("shell32.dll", SetLastError = true)]
        private static extern void SetCurrentProcessExplicitAppUserModelID([MarshalAs(UnmanagedType.LPWStr)] string AppID);

        static void Main(string[] args)
        {
            // Define o AppID exclusivo para a barra de tarefas do Windows
            try
            {
                SetCurrentProcessExplicitAppUserModelID("LucasAosf.PeriquitoAI.Cockpit");
            }
            catch { }

            string appDir = AppDomain.CurrentDomain.BaseDirectory;
            string mainPy = Path.Combine(appDir, "main.py");

            // Verifica se o servidor já está rodando
            bool isRunning = false;
            try
            {
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:7860/api/status");
                req.Timeout = 1000;
                using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
                {
                    if (resp.StatusCode == HttpStatusCode.OK) isRunning = true;
                }
            }
            catch { isRunning = false; }

            // Se não estiver rodando, inicia o Python em segundo plano totalmente invisível
            if (!isRunning)
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = "python.exe";
                psi.Arguments = "\"" + mainPy + "\" --cockpit";
                psi.WorkingDirectory = appDir;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                psi.WindowStyle = ProcessWindowStyle.Hidden;

                try
                {
                    Process.Start(psi);
                    Thread.Sleep(1800); // Aguarda o servidor subir
                }
                catch (Exception ex)
                {
                    // Fallback para o python no PATH ou padrão
                }
            }

            // Abre a janela do aplicativo nativo via Microsoft Edge App Mode
            ProcessStartInfo edgePsi = new ProcessStartInfo();
            edgePsi.FileName = "msedge.exe";
            edgePsi.Arguments = "--app=http://127.0.0.1:7860 --window-size=1260,860 --app-id=PeriquitoAI";
            edgePsi.UseShellExecute = true;

            try
            {
                Process.Start(edgePsi);
            }
            catch
            {
                // Fallback para navegador padrão
                Process.Start("http://127.0.0.1:7860");
            }
        }
    }
}
