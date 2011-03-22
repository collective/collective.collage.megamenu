from Acquisition import aq_inner

from zope.interface import noLongerProvides, alsoProvides
from zope.component import getMultiAdapter, queryUtility

from Products.Five import BrowserView

from Products.Collage.interfaces import ICollageEditLayer
from Products.statusmessages.interfaces import IStatusMessage
from plone.registry.interfaces import IRegistry

from Products.CMFCore.utils import getToolByName

from collective.collage.megamenu.interfaces import IMegamenuCapable, IMegamenuEnabled, IMegamenuSettings
from collective.collage.megamenu import message_factory as _

from plone.memoize.instance import memoize

### Menu Renderer view

class MenuRenderer(BrowserView):

    def __init__(self, context, request):
        self.context = aq_inner(context)
        self.request = request
        portal_state = getMultiAdapter((context, request), name="plone_portal_state")
        self.portal_url = portal_state.portal_url()
        self.settings = getMultiAdapter((context, request), name="megamenu-settings")

    def getItems(self):
        ajax = self.settings.ajax
        # TODO: Restrict items?
        contents = self.context.getFolderContents()
        
        # Before getting items (actually, before rendering them), remove ICollageEditLayer from request
        composing = ICollageEditLayer.providedBy(self.request)
        if composing:
            noLongerProvides(self.request, ICollageEditLayer)
            
        current_url = self.request.get('ACTUAL_URL') + '/'
        items = []
        for content in contents:
            item = {}
            item['id'] = content.getId
            item['object'] = content
            is_collage = content.meta_type == 'Collage'
            if is_collage:
                collage = content.getObject()
                
            item['with_menu'] = is_collage
            item['title'] = content.Title or ''
            item['description'] = content.Description or ''
            if content.meta_type == 'ATLink':
                # For ATLinks, get the link
                remoteUrl = content.getRemoteUrl
                if remoteUrl[0] == '/':
                    item['url'] = '%s%s' % (self.portal_url, remoteUrl)
                else:
                    item['url'] = remoteUrl
            else:
                # For other contents, get its url
                item['url'] = content.getURL()
                if is_collage:
                    # Bug if it's a Collage, try to get its first related item
                    related = collage.getRelatedItems()
                    if len(related)>0:
                        item['url'] = related[0].absolute_url();


            # Should item be rendererd as 'selected'?
            # 1. item.url==portal_url and current_url==item.url
            # 2. item.url!=portal_url and current_url.startswith(item.url)
            if (item['url']==self.portal_url+'/' and current_url==item['url']) or \
               (item['url']!=self.portal_url+'/' and current_url.startswith(item['url'])):
                item['selected_class'] = 'selected'
            else:
                item['selected_class'] = ''
                
            if is_collage:
                item['class'] = 'menu-dropdown'
                if not ajax:
                    item['dropdown'] = collage.restrictedTraverse('@@menu-renderer')()
                    item['deferred'] = ''
                else:
                    item['dropdown'] = ''
                    item['deferred'] = '%s%s' % (content.getURL(), '/@@menu-renderer')
            else:
                item['class'] = ''
                item['dropdown'] = None
                item['deferred'] = ''
                
            items.append(item)

        if composing:
            alsoProvides(self.request, ICollageEditLayer)
            
        return items

## Enabler/Disabler View
class EnablerView(BrowserView):

    def __init__(self, context, request):
        self.context = aq_inner(context)
        self.request = request

    def enable(self):
        message = ""

        if not self.is_enabled():
            alsoProvides(self.context, IMegamenuEnabled)
            message = _(u"Folder can now be used as megamenu")

        self.return_with_message(message)


    def disable(self):
        message = ""

        if self.is_enabled():
            noLongerProvides(self.context, IMegamenuEnabled)
            message = _(u"Folder can no longer be used as megamenu")

        self.return_with_message(message)

    @memoize
    def is_capable(self):
        return IMegamenuCapable.providedBy(self.context)

    @memoize
    def is_enabled(self):
        return IMegamenuEnabled.providedBy(self.context)

    def is_disabled(self):
        return not self.is_enabled()

    def return_with_message(self, message):
        request = self.request

        if message:
            self.context.reindexObject(idxs=['object_provides', ])
            IStatusMessage(request).addStatusMessage(message)

        return request.response.redirect(request.HTTP_REFERER)

## Configuration options View
class SettingsView(BrowserView):

    def __init__(self, context, request):
        self.context = aq_inner(context)
        self.request = request
        registry = queryUtility(IRegistry)
        settings = registry.forInterface(IMegamenuSettings)
        self.enabled = settings.enabled and settings.megamenu_folder
        self.menufolder = None
        if self.enabled:
            catalog = getToolByName(self.context, 'portal_catalog')
            brain = catalog(UID=settings.megamenu_folder)
            if len(brain)>0:
                try:
                    self.menufolder = brain[0].getObject()
                except:
                    pass

        self.ajax = settings.deferred_rendering

