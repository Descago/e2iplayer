# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSearchHistoryHelper, remove_html_markup, GetLogoDir, GetCookieDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
import Plugins.Extensions.IPTVPlayer.libs.urlparser as urlparser
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import time
import re
import urllib
import string
import random
import base64
from copy import deepcopy
from hashlib import md5
try:    import json
except Exception: import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    return optionList
###################################################

def gettytul():
    return 'http://moovie.cc/'

class MoovieCC(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'moovie.cc', 'cookie':'moovie.cc.cookie', 'cookie_type':'MozillaCookieJar'})
        self.DEFAULT_ICON_URL = 'http://www.moovie.cc/images/logo.png'
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        self.MAIN_URL = 'http://www.moovie.cc/'
        self.cacheLinks    = {}
        self.cacheSortOrder = []
        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
    
        self.MAIN_CAT_TAB = [{'category':'list_movies',     'title': _('Movies'),  'url':self.getFullUrl('/online-filmek/')   },
                             {'category':'list_series',     'title': _('Series'),  'url':self.getFullUrl('/online-sorozatok/')},
                             
                             {'category':'search',            'title': _('Search'), 'search_item':True,},
                             {'category':'search_history',    'title': _('Search history'),            } 
                            ]
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)
            
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data
        
    def listItems(self, cItem, nextCategory):
        printDBG("MoovieCC.listItems")
        url = cItem['url']
        sort = cItem.get('f_sort', '')
        
        cItem = dict(cItem)
        if cItem.get('f_query', '') == '':
            sts, data = self.getPage(cItem['url'])
            if not sts: return
            cItem['f_page'] = 1
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="content">', '<script')[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<input', '>')
            inputCache = {}
            cItem['filters'] = []
            for item in tmp:
                name  = self.cm.ph.getSearchGroups(item, '''name=['"]([^"^']+?)['"]''')[0]
                if name == '': continue
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^"^']+?)['"]''')[0]
                inputCache[name] = value
            tmp = self.cm.ph.getDataBeetwenMarkers(data, 'function dataFromInput', '}')[1]
            tmp = re.compile('''\[name=([^\]]+?)\]''').findall(tmp)
            for item in tmp:
                cItem['filters'].append(item)
                if item in ['sort', 'page']: continue
                cItem['f_'+item] = inputCache.get(item,  '')
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '$.ajax(', '});', False)[1]
            cItem['url'] = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''['"]?url['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0])
            cItem['f_query'] = self.cm.ph.getSearchGroups(tmp, '''['"]?data['"]?\s*:\s*['"]([^'^"]+?)['"]''')[0]
        
        # prepare query
        query = []
        for filter in cItem.get('filters', []):
            name = 'f_'+filter
            if name in cItem:
                value = cItem[name]
                if not str(value).startswith(filter+':'):
                    value = '%s:%s' % (filter, cItem[name])
                if not value.endswith('|'): value += '|'
                query.append(value)
        
        query = cItem.get('f_query', '') + (''.join(query))
        
        urlParams = dict(self.defaultParams)
        urlParams.update({'raw_post_data':True})
        sts, data = self.getPage(cItem['url'], urlParams, query)
        if not sts: return
        
        nextPage = self.cm.ph.getSearchGroups(data, '''pages_num\s*=\s*([0-9]+?)[^0-9]''')[0]
        if nextPage != '' and int(nextPage) > 0:
            nextPage = True
        else: nextPage = False
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="movie', '<div class="clear')
        for item in data:
            url = self.getFullUrl( self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0] )
            if not self.cm.isValidUrl(url): continue
            
            icon = self.getFullIconUrl( self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0] )
            title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<a class="title', '</a>')[1] )
            if title == '': title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(item, '''bubble=['"]([^"^']+?)['"]''')[0] )
            if title == '': title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1] )
            desc = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1] )
            
            params = dict(cItem)
            params = {'good_for_fav': True, 'title':title, 'url':url, 'desc':desc, 'icon':icon}
            params['category'] = nextCategory
            self.addDir(params)
        
        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title':_("Next page"), 'f_page':cItem.get('f_page', 1)+1})
            self.addDir(params)
            
    def _listCategories(self, cItem, nextCategory, m1, m2):
        printDBG("MoovieCC._listCategories")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div', '</div>')
        for item in data:
            url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href\s*=\s*['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category':nextCategory, 'title':title, 'url':url})
            self.addDir(params)
        
    def listMovies(self, cItem, nextCategory):
        printDBG("MoovieCC.listMovies")
        self._listCategories(cItem, nextCategory, 'id="get_movies"', '</li>')
        
    def listSeries(self, cItem, nextCategory):
        printDBG("MoovieCC.listSeries")
        self._listCategories(cItem, nextCategory, 'id="get_series"', '</li>')
        
    def listSort(self, cItem, nextCategory):
        printDBG("MoovieCC.listSeries")
        if 0 == len(self.cacheSortOrder):
            sts, data = self.getPage(self.getFullUrl('/online-filmek/')) # sort order is same for movies and series
            if not sts: return
            data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="sort_by">', '</ul>')[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                if not self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0].startswith('javascript'): continue
                sort  = self.cm.ph.getSearchGroups(item, '''id=['"]([^'^"]+?)['"]''')[0]
                if sort == '': continue
                title = self.cleanHtmlStr(item)
                self.cacheSortOrder.append({'title':title, 'f_sort':sort})
        
        for item in self.cacheSortOrder:
            params = dict(cItem)
            params.update({'category':nextCategory})
            params.update(item)
            self.addDir(params)
    
    def _fillLinksCache(self, data, marker):
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, marker, '</table>')
        episodesTab = []
        for tmp in data:
            episodeName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<h2', '</h2>')[1])
            
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<tr', '</tr>')
            for item in tmp:
                url = self.cm.ph.getSearchGroups(item, '''href=['"][^'^"]*/(https?://[^'^"]+?)['"]''')[0]
                if not self.cm.isValidUrl(url): continue
                serverName = []
                item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
                for t in item:
                    if '/flags/' in t:
                        t = self.cm.ph.getSearchGroups(t, '''<img[^>]+?src=['"][^"^']+?/([^/]+?)\.png['"]''')[0]
                    t = self.cleanHtmlStr(t)
                    if t != '': serverName.append(t)
                serverName = ' | '.join(serverName)
                
                if episodeName not in episodesTab:
                    episodesTab.append(episodeName)
                    self.cacheLinks[episodeName] = []
                self.cacheLinks[episodeName].append({'name':serverName, 'url':url, 'need_resolve':1})
        return episodesTab
    
    def exploreItem(self, cItem, nextCategory=''):
        printDBG("MoovieCC.exploreItem")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div id="plot">', '</div>')[1])
        
        # trailer 
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<a id="youtube_video"', '</a>')[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^'^"]+?)['"]''')[0])
        if 1 == self.up.checkHostSupport(url):
            title = self.cleanHtmlStr(tmp)
            title = '%s - %s' %(cItem['title'], title)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title':title, 'prev_title':cItem['title'], 'url':url, 'prev_url':cItem['url'], 'prev_desc':cItem.get('desc', ''), 'desc':desc})
            self.addVideo(params)
        
        sourcesLink = self.cm.ph.getDataBeetwenMarkers(data, '<div class="streamBtn"', '</div>', caseSensitive=False)[1]
        sourcesLink = self.cm.ph.getSearchGroups(sourcesLink, '''href=['"](https?://[^'^"]+?)['"]''')[0]
        if not self.cm.isValidUrl(sourcesLink):
            printDBG("MoovieCC.exploreItem - missing link for sources")
            return
        
        sts, data = self.getPage(sourcesLink)
        if not sts: return []
        
        desc2 = self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>')[1]
        mainTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(desc2, '<h1>', '</h1>')[1])
        if mainTitle == '': mainTitle = cItem['title']
        
        self.cacheLinks  = {}
        
        if 'seasonList' in data:
            # list seasons
            data = self.cm.ph.getDataBeetwenMarkers(data, '<nav>', '</nav>')[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                if url != '' and not self.cm.isValidUrl(url): 
                    url = urlparse.urljoin(sourcesLink, url)
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category':nextCategory, 'title':title, 'prev_title':mainTitle, 'url':url, 'prev_url':cItem['url'], 'prev_desc':cItem.get('desc', ''), 'desc':desc})
                self.addDir(params)
        else:
            desc2 = self.cleanHtmlStr(desc2)
            if desc2 != '': desc = desc2
            episodesList = self._fillLinksCache(data, '<table')
            for item in episodesList:
                params = dict(cItem)
                params.update({'good_for_fav': False, 'links_key':item, 'title':mainTitle, 'desc':desc})
                self.addVideo(params)
            
    def listEpisodes(self, cItem):
        printDBG("MoovieCC.listEpisodes")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>')[1])
        
        seriesTitle = cItem.get('prev_title', '')
        sNum = self.cm.ph.getSearchGroups(cItem['title'], '''^([0-9]+?)\.''')[0]
        
        episodesList = self._fillLinksCache(data, '<div class="item">')
        for item in episodesList:
            eNum = self.cm.ph.getSearchGroups(item, '''^([0-9]+?)\.''')[0]
            params = dict(cItem)
            title = seriesTitle 
            if eNum != '' and sNum != '': 
                title = '%s - s%se%s' % (seriesTitle, sNum.zfill(2), eNum.zfill(2))
            else:
                title = '%s - %s, %s' % (seriesTitle, cItem['title'], item)
            params.update({'good_for_fav': False, 'title':title, 'links_key':item, 'prev_desc':cItem.get('desc', ''), 'desc':desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MoovieCC.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/core/ajax/movies.php')
        cItem['f_query'] = 'type=search&query=keywords:%s|' % searchPattern
        cItem['f_page'] = 1
        cItem['filters'] = ['page']
        self.listItems(cItem, 'explore_item')
        
    def getLinksForVideo(self, cItem):
        printDBG("MoovieCC.getLinksForVideo [%s]" % cItem)
        retTab = []
        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)
        key = cItem.get('links_key', '')
        return self.cacheLinks.get(key, [])
        
    def getVideoLinks(self, videoUrl):
        printDBG("MoovieCC.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []
        orginUrl = str(videoUrl)
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break
                        
        try:
            httpParams = dict(self.defaultParams)
            httpParams['return_data'] = False
            
            sts, response = self.cm.getPage(videoUrl, httpParams)
            videoUrl = response.geturl()
            response.close()
        except Exception:
            printExc()
            return []
        
        if self.up.getDomain(self.getMainUrl()) in videoUrl or self.up.getDomain(videoUrl) == self.up.getDomain(orginUrl):
            sts, data = self.getPage(videoUrl)
            if not sts: return []
            
            found = False
            printDBG(data)
            tmp = re.compile('''<iframe[^>]+?src=['"]([^"^']+?)['"]''', re.IGNORECASE).findall(data)
            for url in tmp:
                if 1 == self.up.checkHostSupport(url):
                    videoUrl = url
                    found = True
                    break
            if not found or 'flashx' in videoUrl:
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, 'embedFrame', '</a>')
                for urlItem in tmp:
                    url = self.cm.ph.getSearchGroups(urlItem, '''href=['"](https?://[^'^"]+?)['"]''')[0]
                    if 1 == self.up.checkHostSupport(url):
                        videoUrl = url
                        found = True
                        break
        
        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        
        return urlTab
    
    def getFavouriteData(self, cItem):
        printDBG('MoovieCC.getFavouriteData')
        return json.dumps(cItem) 
        
    def getLinksForFavourite(self, fav_data):
        printDBG('MoovieCC.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception: printExc()
        return links
        
    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('MoovieCC.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception: 
            params = {}
            printExc()
        self.addDir(params)
        return True
        
    def getArticleContent(self, cItem):
        printDBG("MoovieCC.getArticleContent [%s]" % cItem)
        retTab = []
        
        otherInfo = {}
        
        url = cItem.get('prev_url', '')
        if url == '': url = cItem.get('url', '')
        
        sts, data = self.getPage(url)
        if not sts: return retTab
        
        
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''<meta[^>]+?itemprop="name"[^>]+?content="([^"]+?)"''')[0])
        icon  = self.cm.ph.getDataBeetwenMarkers(data, '<div id="poster"', '</div>')[1]
        icon  = self.getFullIconUrl( self.cm.ph.getSearchGroups(icon, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0] )
        desc  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div id="plot"', '</div>')[1])
        
        rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<span class="rating_all"', '</div>')[1])
        
        data = self.cm.ph.getDataBeetwenMarkers(data, '<table style="margin-left', '</table>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        mapDesc = {'Eredeti Cím:': 'alternate_title', 'Év:':'year', 'Játékidő:':'duration', 'IMDb értékelés:':'imdb_rating',
                   'Kategória:':'category', 'Írta:':'writers', 'Rendezte:':'directors', 'Szereplők:':'actors'} #'Megtekintve:':'views',
        for item in data:
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')
            if len(item) != 2: continue
            marker = self.cleanHtmlStr(item[0])
            tmp  =  self.cm.ph.getAllItemsBeetwenMarkers(item[1], '<a', '</a>')
            value = []
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '': value.append(t)
            if len(value): value = ', '.join(value)
            else: value = self.cleanHtmlStr(item[1])
            if value == '': continue
            key = mapDesc.get(marker, '')
            if key != '': otherInfo[key] = value
            
        if rating != '': otherInfo['rating'] = rating
        
        if title == '': title = cItem['title']
        if desc == '':  desc = cItem.get('desc', '')
        if icon == '':  icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self.getFullUrl(icon)}], 'other_info':otherInfo}]
    
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.cacheLinks = {}
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
        elif category == 'list_movies':
            self.listMovies(self.currItem, 'list_sort')
        elif category == 'list_series':
            self.listSeries(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MoovieCC(), True, [])
        
    def withArticleContent(self, cItem):
        if (cItem['type'] != 'video' and cItem['category'] != 'explore_item'):
            return False
        return True
    
    