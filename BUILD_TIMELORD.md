# Building timelords

The Linux and MacOS melativdf binary wheels currently exclude an executable
required to run a [Timelord](https://github.com/Chia-Network/melati-blockchain/wiki/Timelords).
If you want to run a Timelord on Linux or MacOS, you must install the wheel
from source (which may require some additional development packages) while in
the virtual environment.

```bash
. ./activate

chmod +x ./install-timelord.sh
sh install-timelord.sh
```

If the compile fails, it's likely due to a missing dependency. The script
[install-timelord.sh](https://github.com/Chia-Network/melati-blockchain/blob/main/install-timelord.sh)
attempts to install required build dependencies for Linux and MacOS before
invoking pip to build from the source python distribution of melativdf.

The `install-timelord.sh` install script leverages two environmental variables
that the melativdf wheels can use to specify how to build. The service that the
Timelord uses to run the VDF and prove the Proof of Time is `vdf_client` and
`vdf_bench` is a utility to get a sense of a given CPU's iterations per second.

- To build vdf_client set the environment variable BUILD_VDF_CLIENT to "Y".
`export BUILD_VDF_CLIENT=Y`.
- Similarly, to build vdf_bench set the environment variable BUILD_VDF_BENCH
to "Y". `export BUILD_VDF_BENCH=Y`.

Building and running Timelords in Windows x86-64 is not yet supported.
