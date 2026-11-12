// Copyright (c) 2026 Nemoterm contributors. MIT license.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cwchar>
#include <string>

extern "C" int WINAPI NemoGuiMain(HINSTANCE, HINSTANCE, LPSTR, int);
int CALLBACK NemoConsoleMain(HINSTANCE, HINSTANCE, PWSTR, int);

int CALLBACK wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show)
{
    // The linked ConPTY launches this exact image with --headless first.
    // OpenConsole validates the inherited ConDrv server handle before use.
    // Arguments following -e belong to the shell and never select this mode.
    const auto p = command + std::wcsspn(command, L" \t");
    if (std::wcscmp(p, L"--licenses") == 0)
    {
        const auto resource = FindResourceW(instance, MAKEINTRESOURCEW(40000), RT_RCDATA);
        const auto data = LoadResource(instance, resource);
        const auto size = SizeofResource(instance, resource);
        DWORD written = 0;
        if (!data || !WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), LockResource(data), size, &written, nullptr) || written != size)
            return ERROR_WRITE_FAULT;
        return 0;
    }
    if (std::wcsncmp(p, L"--headless", 10) == 0 &&
        (p[10] == L' ' || p[10] == L'\t' || p[10] == L'\0'))
    {
        return NemoConsoleMain(instance, previous, command, show);
    }
    // Keep PuTTY's special saved-session/file-mapping prefixes working too.
    const auto length = WideCharToMultiByte(CP_ACP, 0, command, -1, nullptr, 0, nullptr, nullptr);
    if (!length)
        return static_cast<int>(GetLastError());
    std::string legacy(static_cast<size_t>(length), '\0');
    WideCharToMultiByte(CP_ACP, 0, command, -1, legacy.data(), length, nullptr, nullptr);
    return NemoGuiMain(instance, previous, legacy.data(), show);
}
