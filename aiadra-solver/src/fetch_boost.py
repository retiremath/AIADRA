# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 AIADRA
"""Locked Boost acquisition for the AIADRA planegcs package (no pip needed).

Downloads the pinned archive, verifies its sha256, extracts ONLY the boost/
header tree to src/boost, and verifies the BSL-1.0 license text.
"""
import hashlib
import io
import os
import tarfile
import urllib.request

URL = "https://archives.boost.io/release/1.86.0/source/boost_1_86_0.tar.gz"
SHA256 = "2575e74ffc3ef1cd0babac2c1ee8bdb5782a0ee672b1912da40e5b4b591ca01f"
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    dst = os.path.join(HERE, "boost")
    if os.path.isdir(dst):
        print("src/boost already present; nothing to do")
        return
    archive = os.path.join(HERE, "boost_1_86_0.tar.gz")
    if not os.path.isfile(archive):
        print("downloading", URL)
        urllib.request.urlretrieve(URL, archive)
    h = hashlib.sha256()
    with open(archive, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != SHA256:
        raise SystemExit(f"sha256 mismatch: {h.hexdigest()} != {SHA256}")
    print("archive sha256 verified; extracting boost/ headers (be patient)")
    with tarfile.open(archive, "r:gz") as tf:
        lic = tf.extractfile("boost_1_86_0/LICENSE_1_0.txt").read()
        if b"Boost Software License" not in lic:
            raise SystemExit("BSL-1.0 license text not found in archive")
        members = [m for m in tf.getmembers()
                   if m.name.startswith("boost_1_86_0/boost/")]
        for m in members:
            m.name = m.name.replace("boost_1_86_0/boost/", "boost/", 1)
        tf.extractall(HERE, members=members, filter="data")
    os.remove(archive)
    print("src/boost ready; license verified")

if __name__ == "__main__":
    main()
