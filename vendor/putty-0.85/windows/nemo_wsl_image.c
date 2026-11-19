/* The distribution is one PE. A Linux guest needs a regular executable on
 * its filesystem, so keep one verified file for exactly this WSL session. */
#include "nemo_wsl_image.h"
#include <objbase.h>

static bool same_file(const BY_HANDLE_FILE_INFORMATION *a,
                      const BY_HANDLE_FILE_INFORMATION *b)
{
    return a->dwVolumeSerialNumber == b->dwVolumeSerialNumber &&
        a->nFileIndexHigh == b->nFileIndexHigh && a->nFileIndexLow == b->nFileIndexLow;
}

DWORD nemo_wsl_image_close(NemoWslImage *image)
{
    if (!image->path) return ERROR_SUCCESS;
    if (image->reader && image->reader != INVALID_HANDLE_VALUE) CloseHandle(image->reader);
    DWORD err = ERROR_SUCCESS;
    HANDLE file = CreateFileW(image->path, DELETE | FILE_READ_ATTRIBUTES,
                              FILE_SHARE_READ | FILE_SHARE_DELETE, NULL, OPEN_EXISTING,
                              FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        err = GetLastError();
        if (err == ERROR_FILE_NOT_FOUND) err = ERROR_SUCCESS;
    } else {
        BY_HANDLE_FILE_INFORMATION id;
        FILE_DISPOSITION_INFO remove = { TRUE };
        if (!GetFileInformationByHandle(file, &id)) err = GetLastError();
        else if (!same_file(&image->identity, &id)) err = ERROR_FILE_INVALID;
        else if (!SetFileInformationByHandle(file, FileDispositionInfo, &remove, sizeof(remove))) err = GetLastError();
        CloseHandle(file);
    }
    sfree(image->path); memset(image, 0, sizeof(*image));
    return err;
}

DWORD nemo_wsl_image_open(NemoWslImage *image)
{
    HMODULE module = GetModuleHandleW(NULL);
    HRSRC res = FindResourceW(module, MAKEINTRESOURCEW(40003), MAKEINTRESOURCEW(10));
    if (!res) return GetLastError();
    DWORD size = SizeofResource(module, res);
    if (!size) return ERROR_BAD_FORMAT;
    HGLOBAL data = LoadResource(module, res);
    const unsigned char *bytes = data ? LockResource(data) : NULL;
    if (!bytes) return ERROR_RESOURCE_DATA_NOT_FOUND;
    GUID guid; wchar_t id[40];
    if (FAILED(CoCreateGuid(&guid)) || !StringFromGUID2(&guid, id, lenof(id))) return ERROR_GEN_FAILURE;
    wchar_t *temp = snewn(32768, wchar_t);
    DWORD n = GetTempPathW(32768, temp);
    if (!n || n >= 32768) { sfree(temp); return ERROR_PATH_NOT_FOUND; }
    wchar_t *path = dupwcscat(temp, L"nemoterm-wsl-", id, L".elf"); sfree(temp);
    HANDLE file = CreateFileW(path, GENERIC_WRITE | DELETE, 0, NULL, CREATE_NEW,
                              FILE_ATTRIBUTE_TEMPORARY, NULL);
    if (file == INVALID_HANDLE_VALUE) { DWORD err = GetLastError(); sfree(path); return err; }
    DWORD written = 0, err = ERROR_SUCCESS;
    if (!GetFileInformationByHandle(file, &image->identity) || !WriteFile(file, bytes, size, &written, NULL))
        err = GetLastError();
    else if (written != size) err = ERROR_WRITE_FAULT;
    if (err) {
        FILE_DISPOSITION_INFO remove = { TRUE };
        SetFileInformationByHandle(file, FileDispositionInfo, &remove, sizeof(remove));
        CloseHandle(file); sfree(path); return err;
    }
    CloseHandle(file);
    image->path = path;
    image->reader = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                                FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (image->reader == INVALID_HANDLE_VALUE) err = GetLastError();
    else {
        BY_HANDLE_FILE_INFORMATION check;
        if (!GetFileInformationByHandle(image->reader, &check)) err = GetLastError();
        else if (!same_file(&image->identity, &check) || check.nFileSizeHigh || check.nFileSizeLow != size ||
                 (check.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) err = ERROR_FILE_INVALID;
        for (DWORD at = 0; !err && at < size; ) {
            unsigned char buf[4096]; DWORD count = min(size-at, (DWORD)sizeof(buf)), got;
            if (!ReadFile(image->reader, buf, count, &got, NULL)) err = GetLastError();
            else if (got != count || memcmp(buf, bytes+at, count)) err = ERROR_INVALID_DATA;
            at += count;
        }
    }
    if (err) nemo_wsl_image_close(image);
    return err;
}
