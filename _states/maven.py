'''
Gets artifact from Maven repository
'''
from xml.etree import ElementTree
import os
import re
#import urllib
#import urlparse
import requests


# https://regex101.com/r/O5WKkh/2
RE_1 = r'^(?P<lbrace>\(|\[)\s*(?P<from>(\d+(?:\.\d+){0,2})(?:-\w*)?)?\s*,\s*(?P<to>(\d+(?:\.\d+){0,2})(?:-\w*)?)?\s*(?P<rbrace>\)|\])$'
RE_2 = r'^(?P<major>\d+)(?:\.(?P<minor>\d+)(?:\.(?P<micro>\d+))?)?(?:-(?P<qualifier>\w+))?$'

def get(name,
        repo_url='https://repo1.maven.org/maven2/',
        group_id=None,
        artifact_id=None,
        version=None,
        classifier='',
        artifact_type='jar',
        save_to=None,
        unarchive=False,
        **kwargs):
    '''
    Get latest artifact from Maven repository and saves it
    to the direcotry defined in `save_to` or `name` or as
    a file `save_as`.

    name:
        Either some logical name (if `save_to` is defined) or
        the directory to save the file of Maven artifact to.
    repo_url : https://repo1.maven.org/maven2/
        repository url
    group_id
        group of the artifactId
    artifact_id
        ID of the artifact
    version
        Optional. Version of artifact, otherwise latest.
    classifier
        Optional. Artifact's classifier
    artifact_type : jar
        Optional. Artifact type (file extension) - default is `jar`.
    save_to:
        Optional. Directory to save the artifact to. If defined then
        `name` is ignored as location.
    save_as:
        Optional. Saves artifact as a specified file. Overrides `save_to`.
    unarchive:
        Optional. Unarchive to the directory specified.
        If `True` - extract to directory with archive.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': '',
        'pchanges': {},
        }

    mvnkwargs = {}

    for kwarg in kwargs.keys():
        mvnkwargs[kwarg] = kwargs[kwarg]

    if group_id is None:
        ret['result'] = False
        ret['comment'] = '"group_id" MUST be specified in salt.state.maven'

    if artifact_id is None:
        ret['result'] = False
        ret['comment'] = '"artifact_id" MUST be specified in salt.state.maven'

    if version is None:
        version = _get_latest_version(repo_url, group_id, artifact_id)

    if artifact_type is None:
        artifact_type = 'jar'
    save_as = mvnkwargs['save_as']
    if save_as is None or len(save_as) == 0:
        if save_to is None or len(save_to) == 0:
            save_to = name
        #if os.path.isdir(save_to) == False:
        #    ret['comment'] = '"save_to" : {} - is not a valid directory'.format(save_to)
        #    ret['result'] = False
        #    return ret
        save_as = '{}/{}.{}'.format(save_to.rstrip('/'), artifact_id, artifact_type)

    save_as = _to_absolute_path(save_as)
    print('Artifcat will be saved as: {}'.format(save_as))
    artifact_url = _get_artifact_url(
        repo_url, group_id, artifact_id, version, classifier, artifact_type)
    current_state = __salt__['data.get'](artifact_url)
    #artifact_is_already_downloaded = __salt__['file.file_exists'](save_to)
    if current_state == save_as and __salt__['file.file_exists'](save_as) is True:
        # add md5 check...
        ret['result'] = True
        ret['comment'] = 'Artifact from {} is already saved in file {}'.format(
            artifact_url, save_as)
        return ret

    #Test mode
    if __opts__['test'] is True:
        ret['comment'] = 'The state of "{0}" will be changed.'.format(name)
        if current_state is None:
            old_state = {}
        else:
            old_state = {'artifact_url':artifact_url, 'save_as':current_state}
        ret['pchanges'] = {
            'old': old_state,
            'new': {'artifact_url':artifact_url, 'save_as':save_as}
        }
        ## Return ``None`` when running with ``test=true``.
        ret['result'] = None
        return ret

    # Finally, make the actual change and return the result.
    artifact_file_operation = __states__['file.managed'](
        name=save_as, source=artifact_url, source_hash='{}.md5'.format(artifact_url),
        makedirs=True)

    if artifact_file_operation['result'] is False:
        ret['result'] = False
        #raise salt.exceptions.SaltInvocationError(
        # 'Failed to downlad artifact: {}'.format(fileReturn['comment']))
        ret['comment'] = 'Failed to downlad artifact: {}'.format(artifact_file_operation['comment'])
        return ret

    #new_state = __salt__['maven.change_state'](name, {'urlToLoad':urlToLoad, 'saveTo':saveTo})
    __salt__['data.update'](artifact_url, save_as)
    ret['comment'] = 'The state of "{0}" was changed! {1} is loaded to {2}'.format(
        name, artifact_url, save_as)
    # unarchive
    if unarchive is not False:
        if unarchive is True:
            unarchive_dir = os.path.dirname(save_as)
        else:
            unarchive_dir = _to_absolute_path(unarchive)
        if artifact_type == 'tar':
            __salt__['archive.tar']('xf', save_as, dest=unarchive_dir)
        elif artifact_type == 'tar.bz2':
            __salt__['archive.tar']('xjf', save_as, dest=unarchive_dir)
        elif artifact_type == 'tar.gz':
            __salt__['archive.tar']('xzf', save_as, dest=unarchive_dir)
        else:
            __salt__['archive.unzip'](save_as, unarchive_dir)

#        if artifact_type != 'zip' or artifact_type != 'tar' or artifact_type != 'rar':
#            if artifact_type == 'tar.gz':
#                artifact_type = 'tar'
#            elif artifact_type == 'jar':
#                artifact_type = 'zip'
#            else:
#                artifact_type = 'zip'
#        archive = urlparse.urljoin('file:', urllib.pathname2url(save_as))        
#        __states__['archive.extracted'](
#            source=archive, name=unarchive_dir, archive_format=artifact_type, skip_verify=True)
    if current_state is None:
        ret['changes'] = {
            'old': {},
            'new': {
                'artifact_url': artifact_url,
                'save_as': save_as,
                'artifact_file_operation': artifact_file_operation['changes']
            }
        }
    else:
        ret['changes'] = {
            'old': {'artifact_url': artifact_url, 'save_as': current_state},
            'new': {
                'artifact_url': artifact_url,
                'save_as': save_as,
                'artifact_file_operation': artifact_file_operation['changes']
            }
        }
    ret['result'] = True
    return ret

def _get_latest_version(repo_url, group_id, artifact_id):
    '''
    Checks if artifact is snaphsot
    Keyword arguments:
    url -- artifacts URL in Maven repository

    Returns:
        latest version, as string
    '''
    url = '{}/{}/{}/maven-metadata.xml'.format(
        repo_url.rstrip('/'),
        group_id.replace('.', '/'),
        artifact_id
    )
    print('Artifact metadata: {}'.format(url))
    response = requests.get(url)
    print(response.content)
    root = ElementTree.XML(response.content)
    greatest_version = root.find('versioning/versions/version[last()]')
    return greatest_version.text

def _get_versions(repo_url, group_id, artifact_id):
    url = '{}/{}/{}/maven-metadata.xml'.format(
        repo_url.rstrip('/'),
        group_id.replace('.', '/'),
        artifact_id
    )
    print('Artifact metadata: {}'.format(url))
    response = requests.get(url)
    print(response.content)
    version_elements = ElementTree.XML(response.content).findall('versioning/versions/version')
    return [i.text for i in version_elements]

def _get_artifact_url(repo_url,
                      group_id,
                      artifact_id,
                      version,
                      classifier,
                      artifact_type):
    '''
    Gets URL to the latest artifact

    Returns:
        URL to get artifact
    '''
    if version is not None:
        possible_range = version
        version = _normalize_version(repo_url, group_id, artifact_id, version)
        if version is None:
            raise ValueError('Nothing is found in the range {}'.format(possible_range))

    if version is None:
        version = _get_latest_version(repo_url, group_id, artifact_id)
    if version.endswith('-SNAPSHOT'):
        return _get_last_snapshot(
            repo_url, group_id, version, artifact_id, classifier, artifact_type)
    else:
        group_url = '{}/{}'.format(repo_url.rstrip('/'), group_id.replace('.', '/'))
        classifier_marker = '-{}'.format(classifier) if classifier is not None else ''
        return '{}/{}/{}/{}-{}{}.{}'.format(
            group_url, artifact_id, version, artifact_id, version, classifier_marker, artifact_type)


def _get_last_snapshot(repo_url, group_id, version, artifact_id, classifier, artifact_type):
    group_url = '{}/{}'.format(repo_url.rstrip('/'), group_id.replace('.', '/'))
    version_metadata_url = '{}/{}/{}/maven-metadata.xml'.format(group_url, artifact_id, version)
    response = requests.get(version_metadata_url)
    print(response.content)
    root = ElementTree.XML(response.content)
    timestamp = root.find('versioning/snapshot/timestamp')
    buildnumber = root.find('versioning/snapshot/buildNumber')
    marker = '{}-{}'.format(timestamp.text, buildnumber.text)
    snapshot_version = version.replace('SNAPSHOT', marker)
    classifier_marker = '-{}'.format(classifier) if classifier is not None else ''
    return '{}/{}/{}/{}-{}{}.{}'.format(
        group_url, artifact_id, version, artifact_id,
        snapshot_version, classifier_marker, artifact_type)

def _normalize_version(repo_url, group_id, artifact_id, version):
    if version is None:
        return None

    pat_1 = re.compile(RE_1)
    match = re.match(pat_1, version)
    if match is None:
        return version
    versions = _get_versions(repo_url, group_id, artifact_id)
    version_set = set()

    pat_2 = re.compile(RE_2)
    for ver in versions:
        tuple_version = _split_version_string(ver, pat_2)
        if tuple_version is not None:
            version_set.add(tuple_version)
    start_version = _split_version_string(match.group('from'), pat_2)
    maven_set = sorted(version_set, key=lambda tup: (tup[0], tup[1], tup[2], tup[3]))
    print(maven_set)
    if start_version is not None:
        just_bigger = True if match.group('lbrace') == '(' else False
        for mver in maven_set[:]:
            if mver < start_version:
                print('remove [', mver)
                maven_set.remove(mver)
            elif mver == start_version and just_bigger:
                print('remove (', mver)
                maven_set.remove(mver)
    end_version = _split_version_string(match.group('to'), pat_2)
    if end_version is not None:
        just_smaller = True if match.group('rbrace') == ')' else False
        for mver in maven_set[:]:
            if mver > end_version:
                print('remove ]', mver)
                maven_set.remove(mver)
            elif mver == end_version and just_smaller:
                print('remove )', mver)
                maven_set.remove(mver)
    try:
        v_tup = maven_set[-1]
        qualifier = v_tup[3]
        qualifier = '-{}'.format(qualifier) if qualifier is not None else ''
        return '{}.{}.{}{}'.format(v_tup[0], v_tup[1], v_tup[2], qualifier)
    except IndexError:
        return None

def _split_version_string(version, pattern):
    if version is not None:
        match = re.match(pattern, version)
        if match is not None:
            major = match.group('major')
            minor = match.group('minor')
            minor = 0 if minor is None else minor
            micro = match.group('micro')
            micro = 0 if micro is None else micro
            qualifier = match.group('qualifier')
            tuple_arr = map(int, [major, minor, micro])
            tuple_arr.append(qualifier)
            return tuple(tuple_arr)
    return None

def _to_absolute_path(the_path):
    the_path = os.path.expandvars(the_path)
    the_path = os.path.expanduser(the_path)
    return os.path.abspath(the_path)
