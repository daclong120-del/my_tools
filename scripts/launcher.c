#include <process.h>
#include <stdio.h>
#include <windows.h>

int main(int argc, char *argv[]) {
    char exePath[MAX_PATH];
    GetModuleFileNameA(NULL, exePath, MAX_PATH);
    char *lastSlash = strrchr(exePath, '\\');
    if (lastSlash) *lastSlash = '\0';
    
    char targetExe[MAX_PATH];
    snprintf(targetExe, MAX_PATH, "%s\\app_core\\SocialPetaDownloader.exe", exePath);
    
    argv[0] = targetExe;
    intptr_t ret = _spawnvp(_P_WAIT, targetExe, argv);
    return (int)ret;
}
