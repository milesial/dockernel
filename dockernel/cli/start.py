import json
import os
from argparse import Namespace
from pathlib import Path

import docker

from .main import subparsers, set_subcommand_func

arguments = subparsers.add_parser(
    __name__.split('.')[-1],
    help="Start a dockernel."
)

# TODO: add a note about how to pull / build an image
# TODO: add a note about default images
arguments.add_argument(
    'image_name',
    help="Name of the docker image to use."
)

# TODO: make this one optional
# TODO: add a help note about it being put into environment variables
# TODO: add a note about how some kernels react when it is not given
arguments.add_argument(
    'connection_file',
    help="The connection file to use."
)


CONTAINER_CONNECTION_SPEC_PATH = '/kernel-connection-spec.json'
CONTAINER_CONNECTION_SPEC_ENV_VAR = 'DOCKERNEL_CONNECTION_FILE'


def set_connection_ip(connection_file: Path, ip: str = '0.0.0.0'):
    """ Set/update ip field in connection file """

    connection = json.loads(connection_file.read_text())
    connection['ip'] = ip
    connection_file.write_text(json.dumps(connection))

    return connection


def start(parsed_args: Namespace) -> int:
    client = docker.from_env()
    name_split = parsed_args.image_name.split(':')
    if len(name_split) == 2:
        image, tag = name_split
    else:
        image, tag = parsed_args.image_name, None

    client.images.pull(image, tag)
    containers = client.containers
    image_name = parsed_args.image_name
    connection_file = Path(parsed_args.connection_file)

    connection = set_connection_ip(connection_file, '0.0.0.0')
    port_mapping = {connection[k]: connection[k] for k in connection if "_port" in k}

    # TODO: parametrize connection spec file bind path
    connection_file_mount = docker.types.Mount(
        target=CONTAINER_CONNECTION_SPEC_PATH,
        source=str(connection_file.absolute()),
        type='bind',
        # XXX: some kernels still open connection spec in write mode
        # (I'm looking at you, IPython), even though it's not being written
        # into.
        read_only=False
    )

    wd_mount = docker.types.Mount(
        target='/working_dir',
        source=os.getcwd(),
        type='bind',
        read_only=False
    )

    # TODO: parametrize possible mounts
    # TODO: log stdout and stderr
    # TODO: use detached=True?
    containers.run(
        image_name,
        command='python -m ipykernel_launcher -f ' + str(CONTAINER_CONNECTION_SPEC_PATH),
        working_dir='/working_dir',
        privileged=True,
        ipc_mode='host',
        device_requests=[docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])],
        auto_remove=True,
        mounts=[wd_mount, connection_file_mount],
        network_mode='bridge',
        ports=port_mapping,
        stdout=True,
        stderr=True
    )

    # TODO: bare numbered exit statusses seem bad
    return 0


set_subcommand_func(parser=arguments, func=start)
