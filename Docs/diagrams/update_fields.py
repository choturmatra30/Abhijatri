"""Fill the contents list (TOC field) of .docx files with LibreOffice, save them, and export a PDF beside each.

Usage: python3 update_fields.py file.docx [...] [--pdf-dir DIR]
Needs LibreOffice (soffice) and its Python UNO bridge.
"""
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main(args):
    pdf_dir = None
    if "--pdf-dir" in args:
        i = args.index("--pdf-dir")
        pdf_dir = args[i + 1]
        args = args[:i] + args[i + 2:]
    proc = subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore",
                             "--accept=socket,host=localhost,port=2002;urp;"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ctx = uno.getComponentContext()
    resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
    for _ in range(60):
        try:
            remote = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
            break
        except Exception:
            time.sleep(0.5)
    desktop = remote.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", remote)
    try:
        for path in args:
            url = uno.systemPathToFileUrl(os.path.abspath(path))
            doc = desktop.loadComponentFromURL(url, "_blank", 0, (prop("Hidden", True),))
            doc.getDocumentIndexes()  # force layout
            for _ in range(2):  # twice: page numbers settle after the list itself takes space
                idx = doc.getDocumentIndexes()
                for i in range(idx.getCount()):
                    idx.getByIndex(i).update()
                doc.refresh()
            doc.storeToURL(url, (prop("FilterName", "MS Word 2007 XML"),))
            if pdf_dir:
                out = os.path.join(pdf_dir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
                doc.storeToURL(uno.systemPathToFileUrl(os.path.abspath(out)), (prop("FilterName", "writer_pdf_Export"),))
            doc.close(True)
            print("updated", path)
    finally:
        try:
            desktop.terminate()
        except Exception:
            pass
        proc.wait(timeout=30)


if __name__ == "__main__":
    main(sys.argv[1:])
