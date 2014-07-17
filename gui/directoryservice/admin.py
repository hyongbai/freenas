#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
import logging

from django.contrib import admin
from django.utils.translation import ugettext as _

from freenasUI.directoryservice import models
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site

log = logging.getLogger('directoryservice.admin')


class ActiveDirectoryFAdmin(BaseFreeAdmin):
    create_modelform = "ActiveDirectoryForm"
    edit_modelform = "ActiveDirectoryForm"
    icon_object = u"ActiveDirectoryIcon"
    icon_model = u"ActiveDirectoryIcon"
    icon_add = u"ActiveDirectoryIcon"
    icon_view = u"ActiveDirectoryIcon"


class LDAPFAdmin(BaseFreeAdmin):
    create_modelform = "LDAPForm"
    edit_modelform = "LDAPForm"
    icon_object = u"LDAPIcon"
    icon_model = u"LDAPIcon"
    icon_add = u"LDAPIcon"
    icon_view = u"LDAPIcon"


class NISFAdmin(BaseFreeAdmin):
    create_modelform = "NISForm"
    edit_modelform = "NISForm"
    icon_object = u"NISIcon"
    icon_model = u"NISIcon"
    icon_add = u"NISIcon"
    icon_view = u"NISIcon"
 

class NT4FAdmin(BaseFreeAdmin):
    create_modelform = "NT4Form"
    edit_modelform = "NT4Form"
    icon_object = u"NT4Icon"
    icon_model = u"NT4Icon"
    icon_add = u"NT4Icon"
    icon_view = u"NT4Icon"


site.register(models.ActiveDirectory, ActiveDirectoryFAdmin)
site.register(models.LDAP, LDAPFAdmin)
site.register(models.NIS, NISFAdmin)
site.register(models.NT4, NT4FAdmin)