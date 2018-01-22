# -*- coding: utf-8 -*-

# Standard libraries - Python 2 & 3
import re, requests
from multiprocessing.dummy import Pool, cpu_count

try: # Python 3
    import html
except: # Python 2
    from HTMLParser import HTMLParser
    
try: # Python 3
    from urllib import parse
except: # Python 2
    import urllib, urlparse

# Kodi libraries
import xbmc, xbmcplugin, xbmcgui, xbmcaddon

# Identifiers
BASE_URL = sys.argv[0].encode('utf-8')
ADDON_HANDLE = int(sys.argv[1])
addon         = xbmcaddon.Addon()
ADDON_NAME = addon.getAddonInfo('name')

# Convenience
try: # Python 3
    un_escape = html.unescape
except: # Python 2
    un_escape = HTMLParser().unescape

try: # Python 3
    qp = parse.quote_plus
    uqp = parse.unquote_plus
    p_qsl = parse.parse_qsl
except: # Python 2
    qp = urllib.quote_plus
    uqp = urllib.unquote_plus
    p_qsl = urlparse.parse_qsl

# HTTP constants
user_agent = ['Mozilla/5.0 (Windows NT 6.1; Win64; x64)',
                'AppleWebKit/537.36 (KHTML, like Gecko)',
                'Chrome/55.0.2883.87',
                'Safari/537.36']
user_agent = ' '.join(user_agent)
http_headers = {'User-Agent':user_agent, 
            'Accept':"text/html", 
            'Accept-Encoding':'identity', 
            'Accept-Language':'en-US,en;q=0.8',
            'Accept-Charset':'utf-8'
            }

http_timeout = 10

# Where our targets live
domain_home = "https://www.liveleak.com/"

# -----------------
# --- Functions ---
# -----------------

# --- Helper functions ---

def log(txt, level='debug'):
    """
    Write text to Kodi log file.
    :param txt: text to write
    :type txt: str
    """
    levels = {
        'debug': xbmc.LOGDEBUG,
        'error': xbmc.LOGERROR,
        'notice': xbmc.LOGNOTICE
        }
    logLevel = levels.get(level, xbmc.LOGDEBUG)

    message = '%s: %s' % (ADDON_NAME, txt)
    xbmc.log(msg=message, level=logLevel)

def notify(message):
    """
    Execute built-in GUI Notification
    :param message: message to display
    :type message: str
    """
    command = 'XBMC.Notification("%s", "%s", %s)' % (ADDON_NAME, message , 5000)
    xbmc.executebuiltin(command)

def cleanHtml(raw_html):
    pseudo_html = re.sub(r'<br />', '[[br]]', raw_html)
    pseudo_html = re.sub(r'</p>', '[[p]]', pseudo_html)
    raw_text = re.sub(r'<script.*?/script>', '', pseudo_html, flags=re.DOTALL)
    raw_text = re.sub(r'<script.*?/script>', '', raw_text, flags=re.DOTALL)
    raw_text = re.sub(r'<style.*?/style>', '', raw_text, flags=re.DOTALL)
    raw_text = re.sub(r'<.*?>', '', raw_text, flags=re.DOTALL)
    clean_text = re.sub(r'\s{2,}', '', raw_text)
    reformatted_text = clean_text.replace('[[br]]', '\n')
    reformatted_text = reformatted_text.replace('[[p]]', '\n\n')
    return reformatted_text

def addSearch():
    searchStr = ''
    keyboard = xbmc.Keyboard(searchStr, 'Search')
    keyboard.doModal()
    if (keyboard.isConfirmed()==False):
        return
    searchStr=keyboard.getText()
    if len(searchStr) == 0:
        return
    else:
        return searchStr

def addDir(title, queryString):
    if 'browse?' not in queryString:
        queryString = 'browse?' + queryString
    u="%s?mode=indx&url=%s" % (BASE_URL, qp(queryString))
    u=u.encode('utf-8')
    liz=xbmcgui.ListItem(title)
    liz.setInfo(type="Video", infoLabels={"Title": title})
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE,url=u,listitem=liz,isFolder=True)

def findAllMediaItems(page):
    # Consolidate liveleak and Youtube video sources
    liveleakRegexp = r'<source src="(.+?)".*$'
    youtubeRegexp = r'src="//www.youtube.com/embed/(.+?)\?rel=0.*$'
    Regexp = r'%s|%s' % (liveleakRegexp, youtubeRegexp)

    return re.findall(Regexp, page, re.MULTILINE)

def fetchItemDetails((url, thumbnail, title)):
    page = requests.get(url).text
    if page is None: # Silently ignore the page
        return None
    # Get id of liveleak user that posted
    credit = re.findall(r'By:</strong>\s?<a href=".+?">(.+?)</a>', page)
    if credit:
        credit = credit[0]
    else:
        credit = ""
    # Get post description
    description = re.findall(r'<div id="body_text">(.+?)</div>', page, re.DOTALL)
    if description:
        description = cleanHtml(description[0]) #Clean here to reduce footprint
    else:
        description = ""
    
    media = findAllMediaItems(page)
    if media:
        if len(media) > 1:
            mediaList = []
            for medium in media:
                medium = reduce( (lambda x, y: x + y), medium) # Discard unmatched RE
                mediaList.append((url, thumbnail, title, credit, description, medium))
            return mediaList
        else:
            medium = reduce( (lambda x, y: x + y), media[0]) # Discard unmatched RE
            return (url, thumbnail, title, credit, description, medium)

def buildListItem((url, thumbnail, title, credit, description, medium)):
    # Handle possibly multiple-coded html entities
    title = un_escape(un_escape(title.strip()))

    if 'cdn.liveleak.com' in medium:
        # Capture source of this medium
        src = url.replace(domain_home, '')
        url = '%s?mode=play&url=%s&src=%s' % (BASE_URL, qp(medium), qp(src))
    else:
        url = 'plugin://plugin.video.youtube/play/?video_id=%s' % medium

    # Build list item
    liz=xbmcgui.ListItem(label=title, thumbnailImage=thumbnail)
    liz.setInfo(type="Video", infoLabels={"title": title, "credits": credit, "plot": description})
    liz.addStreamInfo('video', {'codec': 'h264'})
    liz.setArt( {'thumb': thumbnail} )
    liz.setProperty('IsPlayable', 'true')

    return (url, liz)

# --- GUI director (Main Event) functions ---

def categories():
    addDir('Popular', 'popular')
    addDir('Featured', 'featured=1')
    addDir('News & Politics', 'channel_token=04c_1302956196')
    addDir('Yoursay', 'channel_token=1b3_1302956579')
    addDir('Must See', 'channel_token=9ee_1303244161')
    addDir('Syria', 'channel_token=cf3_1304149308')
    addDir('Iraq', 'channel_token=e8a_1302956438')
    addDir('Afghanistan', 'channel_token=79f_1302956483')
    addDir('Ukraine', 'channel_token=b80_1390304670')
    addDir('Entertainment', 'channel_token=51a_1302956523')
    addDir('Search', 'q=')

    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def index(url):
    if url=="browse?q=":
        searchString = addSearch()
        url="browse?q="+searchString

    # Flesh out paging
    try:
        appdg = url.split('&')[1] # 'page=X'
        before = url.split('&')[0] # original category path
        nextPageNumber = str(int(appdg.split('=')[1]) + 1) # increment page number
        pagedURL = before + "&page=" + nextPageNumber # reassemble paged url
    except:
        nextPageNumber = '2'
        pagedURL = url + "&page=" + nextPageNumber

    url = domain_home + url
    page = requests.get(url, headers=http_headers, timeout=http_timeout).text
    if page is None:
        notify("The server is not cooperating at the moment")
        return

    # Get list of individual posts from indexing page
    posts=re.findall('<a href="(.+?)"><img class="thumbnail_image" src="(.+?)" alt="(.+?)"', page)

    # Fetch post details via multiple threads
    pool = Pool(cpu_count() * 4)
    items = pool.map(fetchItemDetails, posts)
    pool.close() 
    pool.join()

    if items:
        iList = []
        for item in items: #(url, thumbnail, title, credit, description, medium)
            if isinstance(item, list): # Multiple media on the page
                for idx, atom in enumerate(item):
                    # Rebuild tuple with video number appended to title
                    (url, thumbnail, title, credit, description, medium) = atom
                    title = "%s (%d)" % (title, (idx + 1)) # Add vidNum
                    atom = (url, thumbnail, title, credit, description, medium)
                    (url, liz) = buildListItem(atom)
                    iList.append((url.encode('utf-8'), liz, False))
            else: # Single media item on the page; None if error from fetch
                if item:
                    (url, liz) = buildListItem(item)
                    iList.append((url.encode('utf-8'), liz, False))

        xbmcplugin.addDirectoryItems(ADDON_HANDLE, iList, len(iList))
        addDir("Go To Page " + nextPageNumber, pagedURL)
        liz=xbmcgui.ListItem("Back To Categories")
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE,url=BASE_URL,listitem=liz,isFolder=True)

        xbmcplugin.endOfDirectory(ADDON_HANDLE)

def viewPlay(url):
    url = uqp(url) # Decode html quoted/encoded url

    # Acceptable URL patterns
    url_patterns = [r'liveleak.com/view?', r'liveleak.com/ll_embed?']

    # Verify it's actually a "view" page
    if not any(x in url for x in url_patterns):
        notify("Invalid URL format")
        return

    match = findAllMediaItems(url) # findall match object
    if match:
        # Play first matching media item
        item = match[0]
        item = reduce( (lambda x, y: x + y), item) # Discard unmatched RE
        if not 'cdn.liveleak.com' in item:
            item = 'plugin://plugin.video.youtube/play/?video_id=%s' % item
        play_item = xbmcgui.ListItem(path=item.encode('utf-8'))
        # Pass the item to the Kodi player.
        xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, listitem=play_item)

    else:
        notify("Sorry, no playable media found.")
        return

def playVideo(url, src):
    """
    Play a video by the provided time-based url,
    or fetch new, time-based url from src.
    :param url: Fully-qualified video URL
    :type url: str
    :param src: path of page at domain_home containing video URL
    :type src: str
    """
    # Check if time-based video URL has not expired
    response = requests.head(url, headers=http_headers, timeout=http_timeout)
    content_type = response.headers.get('content-type')

    if content_type is None or u'text/html' not in content_type:
        notify("The server is not cooperating at the moment")
        return False

    # Re-fetch time-based link
    regexp = r'src="(%s\?.+?)"' % url.split('?')[0]
    page = requests.get(domain_home + src, headers=http_headers, timeout=http_timeout).text
    match = re.search(regexp, page)
    if match:
        url = match.group(1)
    else:
        notify("Video has disappeared")
        return False

    # Create a playable item with a url to play.
    play_item = xbmcgui.ListItem(path=url)
    # Pass the item to the Kodi player.
    xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, listitem=play_item)


# ------------------
# --- Main Event ---
# ------------------

# Parse query string into dictionary
try:
    params = dict(p_qsl(sys.argv[2][1:]))
    for key in params:
        try: params[key] = uqp(params[key]).decode('utf-8')
        except: pass
except:
    params = {}

# What do to?
mode = params.get('mode', None)

if mode is None: categories()

elif mode == 'indx':
    url = params.get('url', None) # URL of index folder
    if url: index(url)

elif mode == 'view':
    url = params.get('url', None) # URL of index folder
    if url: viewPlay(url)

elif mode == 'play':
    url = params.get('url', None) # URL of video source
    src = params.get('src', None) # path of page containing video URL
    if url and src: playVideo(url, src)

