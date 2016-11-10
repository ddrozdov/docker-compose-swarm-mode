#!/usr/bin/env python

import argparse
import os
import subprocess
import sys
import threading
from collections import OrderedDict

import yaml
import yodl

debug = False


class DockerCompose:
    def __init__(self, compose, project, compose_base_dir, requested_services):
        self.project = project
        self.compose_base_dir = compose_base_dir
        self.services = self.merge_services(compose.get('services', {}))
        self.networks = compose.get('networks', {})
        self.volumes = compose.get('volumes', {})
        self.filtered_services = filter(lambda service: not requested_services or service in requested_services, self.services)

    def project_prefix(self, value):
        return '{}_{}'.format(self.project, value) if self.project else value

    def merge_services(self, services):
        result = OrderedDict()

        for service in services:
            service_config = services[service]
            result[service] = service_config

            if 'extends' in service_config:
                extended_config = service_config['extends']
                extended_service = extended_config['service']

                del result[service]['extends']

                if 'file' in extended_config:
                    extended_service_data = self.merge_services(
                        yaml.load(open(self.compose_base_dir + extended_config['file'], 'r'), yodl.OrderedDictYAMLLoader)['services']
                    )[extended_service]
                else:
                    extended_service_data = result[extended_service]

                merge(result[service], extended_service_data, None, self.mergeEnv)

        return result

    @staticmethod
    def mergeEnv(a, b, key):
        if key == 'environment':
            if isinstance(a[key], dict) and isinstance(b[key], list):
                a[key] = b[key] + list({'{}={}'.format(k, v) for k, v in a[key].items()})
            elif isinstance(a[key], list) and isinstance(b[key], dict):
                a[key][:0] = list({'{}={}'.format(k, v) for k, v in b[key].items()})
            else:
                raise ('Unknown type of "{}" value (should be either list or dictionary)'.format(key))

    @staticmethod
    def call(cmd, ignore_return_code=False):
        print('Running: \n' + cmd + '\n')
        if not debug:
            ps = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            returncode = ps.wait()
            stdout = ps.communicate()[0]
            if returncode != 0 and not ignore_return_code:
                print >> sys.stderr, ('Error: command "{}" failed: {}'.format(cmd, stdout))
                sys.exit(returncode)
            else:
                return stdout

    def is_service_exists(self, service):
        return self.call('/bin/bash -o pipefail -c "docker service ls | awk \'{{print \\$2}}\' | (egrep \'^{}$\' || :)"'.format(self.project_prefix(service)))

    def is_external_network(self, network):
        if network not in self.networks:
            print >> sys.stderr, ('Error: network "{}" is not defined in networks'.format(network))
            sys.exit(1)
        return isinstance(self.networks[network], dict) and 'external' in self.networks[network]

    def up(self):
        for network in self.networks:
            if not self.is_external_network(network):
                cmd = '[ "`docker network ls | awk \'{{print $2}}\' | egrep \'^{0}$\'`" != "" ] || docker network create --driver overlay --opt encrypted {0}' \
                    .format(self.project_prefix(network))
                self.call(cmd)

        for volume in self.volumes:
            cmd = '[ "`docker volume ls | awk \'{{print $2}}\' | egrep \'^{0}$\'`" != "" ] || docker volume create --name {0}' \
                .format(self.project_prefix(volume))
            if isinstance(self.volumes[volume], dict) and self.volumes[volume]['driver']:
                cmd = cmd + ' --driver={0}'.format(self.volumes[volume]['driver'])
            self.call(cmd)

        services_to_start = []

        for service in self.filtered_services:
            if self.is_service_exists(service):
                services_to_start.append(service)
                continue

            service_config = self.services[service]
            cmd = ['docker service create --with-registry-auth \\\n --name', self.project_prefix(service), '\\\n']

            service_image = []
            service_command = []

            def add_flag(key, value):
                cmd.extend([key, shellquote(value), '\\\n'])

            for parameter in service_config:
                value = service_config[parameter]

                def restart():
                    add_flag('--restart-condition', {'always': 'any'}[value])

                def logging():
                    add_flag('--log-driver', value.get('driver', 'json-file'))
                    log_opts = value['options']
                    if log_opts:
                        for k, v in log_opts.items():
                            if v is not None:
                                add_flag('--log-opt', '{}={}'.format(k, v))

                def mem_limit():
                    add_flag('--limit-memory', value)

                def image():
                    service_image.append(value)

                def command():
                    if isinstance(value, list):
                        service_command.extend(value)
                    else:
                        service_command.extend(value.split(' '))

                def expose():
                    pass  # unsupported

                def container_name():
                    pass  # unsupported

                def hostname():
                    pass  # unsupported; waiting for https://github.com/docker/docker/issues/24877

                def labels():
                    value = service_config[parameter]
                    # ^ working-around the lack of `nonlocal` statement.
                    if isinstance(value, dict):
                        value = ('%s=%s' % i for i in value.iteritems())

                    for label in value:
                        add_flag('--label', label)

                def mode():
                    add_flag('--mode', value)

                def extra_hosts():
                    pass  # unsupported

                def ports():
                    for port in value:
                        add_flag('--publish', port)

                def networks():
                    for network in value:
                        add_flag('--network', network if self.is_external_network(network) else self.project_prefix(network))

                def volumes():
                    for volume in value:
                        splitted_volume = volume.split(':')
                        src = splitted_volume.pop(0)
                        dst = splitted_volume.pop(0)
                        readonly = 0
                        if splitted_volume and splitted_volume[0] == 'ro':
                            readonly = 1
                        if src.startswith('.'):
                            src = src.replace('.', self.compose_base_dir, 1)

                        if src.startswith('/'):
                            add_flag('--mount', 'type=bind,src={},dst={},readonly={}'.format(src, dst, readonly))
                        else:
                            add_flag('--mount', 'src={},dst={},readonly={}'.format(self.project_prefix(src), dst, readonly))

                def environment():
                    if isinstance(value, dict):
                        for k, v in value.items():
                            add_flag('--env', '{}={}'.format(k, v))
                    else:
                        for env in value:
                            if env.startswith('constraint') or env.startswith('affinity'):
                                constraint = env.split(':', 2)[1]
                                add_flag('--constraint', constraint)
                            else:
                                add_flag('--env', env)

                def replicas():
                    add_flag('--replicas', value)

                def env_file():
                    for v in value:
                        with open(v) as env_file:
                            for line in env_file:
                                if not line.startswith('#') and line.strip():
                                    add_flag('--env', line.strip())


                def unsupported():
                    print >> sys.stderr, ('WARNING: unsupported parameter {}'.format(parameter))

                locals().get(parameter, unsupported)()

            if len(service_image) == 0:
                print('ERROR: no image specified for %s service' % service)
                sys.exit(1)

            cmd.extend(service_image)
            cmd.extend(service_command)

            self.call(' '.join(cmd))

        if services_to_start:
            self.start(services_to_start)

    def pull(self):
        nodes = self.call("docker node ls | grep Ready | awk -F'[[:space:]][[:space:]]+' '{print $2}'").rstrip().split('\n')

        threads = []

        for node in nodes:
            cmd = '; '.join(['docker -H tcp://{}:2375 pull {}'.format(node, self.services[service]['image']) for service in self.filtered_services])
            threads.append((node, threading.Thread(target=self.call, args=(cmd,))))

        for node, thread in threads:
            print('Pulling on node {}'.format(node))
            thread.start()

        for node, thread in threads:
            thread.join()
            print('Node {} - DONE'.format(node))

    def stop(self):
        services = filter(self.is_service_exists, self.filtered_services)
        cmd_args = ['{}={}'.format(self.project_prefix(service), 0) for service in services]
        if cmd_args:
            self.call('docker service scale ' + ' '.join(cmd_args))

    def rm(self):
        services = filter(self.is_service_exists, self.filtered_services)
        cmd_args = [self.project_prefix(service) for service in services]
        if cmd_args:
            self.call('docker service rm ' + ' '.join(cmd_args))

    def start(self, services=None):
        if services is None:
            services = self.filtered_services

        cmd = 'docker service scale ' + \
              ' '.join(['{}={}'.format(self.project_prefix(service), self.services[service].get('replicas', '1')) for service in services])
        self.call(cmd)

    def convert(self):
        # Based on http://stackoverflow.com/a/8661021
        represent_dict_order = lambda _self, data: _self.represent_mapping('tag:yaml.org,2002:map', data.items())
        yaml.add_representer(OrderedDict, represent_dict_order)

        def project_prefix(value):
            return '{}-{}'.format(self.project, value) if self.project else value

        if self.networks:
            print >> sys.stderr, ('WARNING: unsupported parameter "networks"')

        for volume in self.volumes:
            print >> sys.stderr, ('WARNING: unsupported parameter "volumes"')

        for service in self.filtered_services:
            service_config = self.services[service]
            service = service.replace('_', '-')
            service_result = OrderedDict([
                ('apiVersion', 'v1'),
                ('kind', 'Service'),
                ('metadata', OrderedDict([
                    ('name', project_prefix(service)),
                    ('labels', OrderedDict())
                ])),
                ('spec', OrderedDict([
                    ('selector', OrderedDict())
                ]))
            ])
            deployment_result = OrderedDict([
                ('apiVersion', 'extensions/v1beta1'),
                ('kind', 'Deployment'),
                ('metadata', OrderedDict([
                    ('name', project_prefix(service))
                ])),
                ('spec', OrderedDict([
                    ('replicas', 1),
                    ('template', OrderedDict([
                        ('metadata', OrderedDict([
                            ('labels', OrderedDict())
                        ])),
                        ('spec', OrderedDict([
                            ('containers', [OrderedDict([
                                ('name', project_prefix(service)),
                            ])])
                        ]))
                    ]))
                ]))
            ])

            service_labels = service_result['metadata']['labels']
            service_selector = service_result['spec']['selector']
            deployment_labels = deployment_result['spec']['template']['metadata']['labels']
            deployment_spec = deployment_result['spec']['template']['spec']
            container = deployment_result['spec']['template']['spec']['containers'][0]

            service_labels['service'] = self.project
            service_labels['app'] = service

            for parameter in service_config:
                value = service_config[parameter]

                def restart():
                    deployment_spec['restartPolicy'] = {'always': 'Always'}[value]

                def logging():
                    pass  # unsupported

                def mem_limit():
                    container['resources'] = {'limits': {'memory': value.replace('m', 'Mi').replace('g', 'Gi')}}

                def image():
                    container['image'] = value

                def command():
                    if isinstance(value, list):
                        container['args'] = value
                    else:
                        container['args'] = value.split(' ')

                def expose():
                    service_result['spec']['ports'] = []
                    container['ports'] = []
                    for port in value:
                        port_int = int(port)
                        service_result['spec']['ports'].append(OrderedDict([('port', port_int), ('targetPort', port_int), ('name', str(port_int))]))
                        container['ports'].append({'containerPort': port_int})

                def container_name():
                    service_result['metadata']['name'] = value
                    deployment_result['metadata']['name'] = value
                    container['name'] = value
                    service_labels['app'] = value

                def hostname():
                    pass  # unsupported

                def labels():
                    pass  # TODO

                def mode():
                    pass  # TODO

                def extra_hosts():
                    pass  # unsupported

                def ports():
                    for port in value:
                        pass  # TODO

                def networks():
                    pass  # unsupported

                def volumes():
                    container['volumeMounts'] = []
                    deployment_spec['volumes'] = []
                    for volume in value:
                        splitted_volume = volume.split(':')
                        src = splitted_volume.pop(0)
                        dst = splitted_volume.pop(0)
                        readonly = 0
                        if splitted_volume and splitted_volume[0] == 'ro':
                            readonly = 1
                        if src.startswith('.'):
                            src = src.replace('.', self.compose_base_dir, 1)

                        if src.startswith('/'):
                            volume_name = src.split('/')[-1].replace('.', '').replace('_', '-')
                            container['volumeMounts'].append(OrderedDict([('name', volume_name), ('mountPath', dst)]))
                            deployment_spec['volumes'].append(OrderedDict([('name', volume_name), ('hostPath', {'path': src})]))
                            # TODO readonly
                        else:
                            volume_name = src.replace('_', '-')
                            container['volumeMounts'].append(OrderedDict([('name', volume_name), ('mountPath', dst)]))
                            deployment_spec['volumes'].append(
                                OrderedDict([('name', volume_name), ('hostPath', {'path': '/volumes/' + project_prefix(volume_name)})]))
                            # TODO readonly

                def environment():
                    if isinstance(value, dict):
                        container['env'] = []
                        for k, v in value.items():
                            container['env'].append(OrderedDict([('name', k), ('value', v)]))
                    else:
                        for env in value:
                            if env.startswith('constraint') or env.startswith('affinity'):
                                if 'nodeSelector' not in deployment_spec:
                                    deployment_spec['nodeSelector'] = OrderedDict()

                                constraint = env.split(':', 2)[1]
                                selector = 'FIX_ME'

                                if constraint.startswith('node.hostname=='):
                                    selector = 'kubernetes.io/hostname'
                                    constraint = constraint.split('==')[1]

                                if constraint.startswith('engine.labels.'):
                                    [selector, constraint] = constraint.split('==')
                                    selector = selector.replace('engine.labels.', '')

                                deployment_spec['nodeSelector'][selector] = constraint
                            else:
                                if 'env' not in container:
                                    container['env'] = []

                                [k, v] = env.split('=')
                                container['env'].append(OrderedDict([('name', k), ('value', v)]))

                def replicas():
                    deployment_result['spec']['replicas'] = int(value)

                def unsupported():
                    print >> sys.stderr, ('WARNING: unsupported parameter {}'.format(parameter))

                locals().get(parameter, unsupported)()

            service_selector.update(service_labels)
            deployment_labels.update(service_labels)

            sys.stdout.write(yaml.dump(service_result, default_flow_style=False))
            print('---')
            sys.stdout.write(yaml.dump(deployment_result, default_flow_style=False))
            print('---')


def main():
    envs = {
        'COMPOSE_FILE': 'docker-compose.yml',
        'COMPOSE_HTTP_TIMEOUT': '60',
        'COMPOSE_TLS_VERSION': 'TLSv1'
    }
    env_path = os.path.join(os.getcwd(), '.env')

    if os.path.isfile(env_path):
        with open(env_path) as env_file:
            envs.update(dict(map(lambda line: line.strip().split('=', 1), (line for line in env_file if not line.startswith('#') and line.strip()))))

    map(lambda e: os.environ.update({e[0]: e[1]}), (e for e in envs.items() if not e[0] in os.environ))

    parser = argparse.ArgumentParser(formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=50, width=120))
    parser.add_argument('-f', '--file', type=argparse.FileType(), help='Specify an alternate compose file (default: docker-compose.yml)', default=[],
                        action='append')
    parser.add_argument('-p', '--project-name', help='Specify an alternate project name (default: directory name)',
                        default=os.environ.get('COMPOSE_PROJECT_NAME'))
    parser.add_argument('--dry-run', action='store_true')
    subparsers = parser.add_subparsers(title='Command')
    parser.add_argument('_service', metavar='service', nargs='*', help='List of services to run the command for')

    services_parser = argparse.ArgumentParser(add_help=False)
    services_parser.add_argument('service', nargs='*', help='List of services to run the command for')

    pull_parser = subparsers.add_parser('pull', help='Pull service images', add_help=False, parents=[services_parser])
    pull_parser.set_defaults(command='pull')

    rm_parser = subparsers.add_parser('rm', help='Stop and remove services', add_help=False, parents=[services_parser])
    rm_parser.set_defaults(command='rm')
    rm_parser.add_argument('-f', help='docker-compose compatibility; ignored', action='store_true')

    start_parser = subparsers.add_parser('start', help='Start services', add_help=False, parents=[services_parser])
    start_parser.set_defaults(command='start')

    stop_parser = subparsers.add_parser('stop', help='Stop services', add_help=False, parents=[services_parser])
    stop_parser.set_defaults(command='stop')

    up_parser = subparsers.add_parser('up', help='Create and start services', add_help=False, parents=[services_parser])
    up_parser.set_defaults(command='up')
    up_parser.add_argument('-d', help='docker-compose compatibility; ignored', action='store_true')

    convert_parser = subparsers.add_parser('convert', help='Convert services to Kubernetes format', add_help=False, parents=[services_parser])
    convert_parser.set_defaults(command='convert')

    args = parser.parse_args(sys.argv[1:])

    if len(args.file) == 0:
        try:
            args.file = map(lambda f: open(f), os.environ['COMPOSE_FILE'].split(':'))
        except IOError as e:
            print(e)
            parser.print_help()
            sys.exit(1)

    global debug
    debug = args.dry_run

    compose_base_dir = os.path.dirname(os.path.abspath(args.file[0].name))

    if args.project_name is None:
        args.project_name = os.path.basename(compose_base_dir)

    # Decode and merge the compose files
    compose_dicts = map(lambda f: yaml.load(f, yodl.OrderedDictYAMLLoader), args.file)
    merged_compose = reduce(merge, compose_dicts)

    docker_compose = DockerCompose(merged_compose, args.project_name, compose_base_dir + '/', args.service)
    getattr(docker_compose, args.command)()


# Based on http://stackoverflow.com/questions/7204805/dictionaries-of-dictionaries-merge/7205107#7205107
def merge(a, b, path=None, conflict_resolver=None):
    """merges b into a"""
    if path is None:
        path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)], conflict_resolver)
            elif isinstance(a[key], list) and isinstance(b[key], list):
                a[key].extend(b[key])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                if conflict_resolver:
                    conflict_resolver(a, b, key)
                else:
                    raise Exception('Conflict at %s' % '.'.join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a

def shellquote(s):
    return "'" + s.replace("'", "'\\''") + "'"

if __name__ == "__main__":
    main()
