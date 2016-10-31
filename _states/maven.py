import requests
import os
from xml.etree import ElementTree

def get(name,
        repoUrl='https://repo1.maven.org/maven2/',
        groupId=None,
        artifactId=None,
        version=None,
        suffix='.jar',
        to=None,
        unzipTo=None,
        **kwargs):
    '''
    Get latest artifact from Maven repository

    name:
        The location of the file to save Maven artifact
    repoUrl : https://repo1.maven.org/maven2/
        repository url
    groupId
        group of the artifactId
    artifactId
        ID of the artifact
    version
        Optional. Version of artifact, otherwise latest.
    suffix : `.jar`
        artifact suffix (.jar, .tar.gz, .zip or yours)
    to:
        Optional. Directory to save the artifact to. If defined `name` is ignored.
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

    if groupId is None:
        ret['result'] = False
        ret['comment'] = 'groupId MUST be specified in salt.state.maven'

    if artifactId is None:
        ret['result'] = False
        ret['comment'] = 'artifactId MUST be specified in salt.state.maven'

    if version is None:
        groupUrl = _getGroupUrl(repoUrl, groupId)
        version = _getLatestVersion( groupUrl , artifactId)

    saveTo = ''
    if (to is None) or (to == ''):
        saveTo = os.path.expandvars(name)
    else:
        to = os.path.expandvars(to)
        if os.path.isdir(to) == False:
            ret['comment'] = 'Specified TO target {0} is not a directory'.format(to)
            ret['result'] = False
            return ret
        saveTo =  '{}/{}-{}{}'.format(to.rstrip('/'), artifactId, version, suffix)

    urlToLoad = _getArtifactUrl(repoUrl, groupId, artifactId, version, suffix)
    current_state = __salt__['data.get'](urlToLoad)
    saveToExists = __salt__['file.file_exists'](saveTo)
    if current_state == saveTo and saveToExists == True:
        ret['result'] = True
        ret['comment'] = 'Artifact from {} is already in file {}'.format(urlToLoad, saveTo)
        return ret

    # Test mode
    if __opts__['test'] == True:
        ret['comment'] = 'The state of "{0}" will be changed.'.format(name)
        if current_state is None:
            oldVal = {}
        else:
            oldVal = {'urlToLoad':urlToLoad, 'saveTo':current_state}
        ret['pchanges'] = {
            'old': oldVal,
            'new': {'urlToLoad':urlToLoad, 'saveTo':saveTo}
        }
        ## Return ``None`` when running with ``test=true``.
        ret['result'] = None
        return ret

    # Finally, make the actual change and return the result.
    fileReturn = __states__['file.managed'](name=saveTo, source=urlToLoad, source_hash='{}.md5'.format(urlToLoad))
    if fileReturn['result'] == False:
        ret['result'] = False
        #raise salt.exceptions.SaltInvocationError('Failed to downlad artifact: {}'.format(fileReturn['comment']))
        ret['comment'] = 'Failed to downlad artifact: {}'.format(fileReturn['comment'])
        return ret

    if(unzipTo is not None):
        unzipTo = os.path.expandvars(unzipTo)
        unzipResult = __salt__['archive.unzip'](zip_file=saveTo,dest=unzipTo)
        if(unzipResult == False):
            ret['result'] == False
            ret['comment'] == unzipResult['comment']
            return ret
        ret['comment'] = 'The state of "{0}" was changed! {1} is loaded to {2}, unzipped to {3}'.format(name, urlToLoad, saveTo, unzipTo)
    else:
        ret['comment'] = 'The state of "{0}" was changed! {1} is loaded to {2}'.format(name, urlToLoad, saveTo)
    # new_state = __salt__['maven.change_state'](name, {'urlToLoad':urlToLoad, 'saveTo':saveTo})
    new_state = __salt__['data.update'](urlToLoad, saveTo)
    if current_state is None:
        ret['changes'] = {
            'old': {},
            'new': {'urlToLoad': urlToLoad, 'saveTo': saveTo, 'fileResult': fileReturn['changes']}
        }
    else:
        ret['changes'] = {
            'old': {'urlToLoad': urlToLoad, 'saveTo': current_state},
            'new': {'urlToLoad': urlToLoad, 'saveTo': saveTo, 'fileResult': fileReturn['changes']}
        }
    ret['result'] = True
    return ret

def _getGroupUrl(repoUrl, groupId):
    return '{}/{}'.format(repoUrl.rstrip('/'),  groupId.replace('.','/'))

def _getLatestVersion(groupUrl, artifactId):
    '''
    Checks if artifact is snaphsot
    Keyword arguments:
    url -- artifacts URL in Maven repository

    Returns:
        latest version, as string
    '''
    url = '{}/{}/maven-metadata.xml'.format(groupUrl, artifactId)
    print url
    response = requests.get(url)
    print response.content
    root = ElementTree.XML(response.content)
    release = root.find("versioning/release")
    if release is None: # SNAPSHOT
        latestSnapshot = root.find("versioning/versions/version[last()]")
        print 'Latest snapshot: {}'.format(latestSnapshot.text)
        return latestSnapshot.text
    else: # RELEASE
        return release.text


def _getArtifactUrl(repoUrl, groupId, artifactId, version, suffix):
    '''
    Gets URL to the latest artifact
    '''
    groupUrl = _getGroupUrl(repoUrl, groupId)
    if version is None:
        version = _getLatestVersion(groupUrl, artifactId)
    if version.endswith('-SNAPSHOT'): # SNAPSHOT
        snapshotUrl = _getLastSnapshot(groupUrl, version, artifactId, suffix)
        return snapshotUrl
    else: # RELEASE
        releaseUrl = '{}/{}/{}/{}-{}{}'.format(groupUrl, artifactId, version, artifactId, version, suffix)
        return releaseUrl


def _getLastSnapshot(groupUrl, version, artifactId, suffix):
    versionMetadataUrl = '{}/{}/{}/maven-metadata.xml'.format(groupUrl, artifactId, version)
    response = requests.get(versionMetadataUrl)
    root = ElementTree.XML(response.content)
    timestamp = root.find("versioning/snapshot/timestamp")
    buildnumber = root.find('versioning/snapshot/buildNumber')
    marker = '{}-{}'.format(timestamp.text, buildnumber.text)
    snapshotVersion = version.replace('SNAPSHOT', marker)
    return '{}/{}/{}/{}-{}{}'.format(groupUrl, artifactId, version, artifactId, snapshotVersion, suffix)

# get('/etc/temp/link.jar', repoUrl='https://repo.1capp.com/nexus/content/repositories/snapshots/', groupId='com.company1c.rap', artifactId='com.company1c.rap.product')
