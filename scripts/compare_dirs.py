import os

def list_files(d):
    res = []
    if not os.path.exists(d): 
        print(f"Directory {d} does not exist!")
        return res
    for root, dirs, files in os.walk(d):
        for f in files:
            res.append(os.path.relpath(os.path.join(root, f), d))
    return sorted(res)

unpacked = list_files(r'd:\Python\my_tools\electron\dist\win-unpacked\resources')
installed = list_files(r'C:\Users\PC\AppData\Local\Programs\my-tools-desktop\resources')

print('Unpacked files count:', len(unpacked))
print('Installed files count:', len(installed))

print('\nOnly in Unpacked:')
for f in unpacked:
    if f not in installed:
        print('  ', f)

print('\nOnly in Installed:')
for f in installed:
    if f not in unpacked:
        print('  ', f)
