#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
from __future__ import with_statement
from plugins import core
from model import api
import re
import os
import pprint
import sys
import random

try:
    import xml.etree.cElementTree as ET
    import xml.etree.ElementTree as ET_ORIG
    ETREE_VERSION = ET_ORIG.VERSION
except ImportError:
    import xml.etree.ElementTree as ET
    ETREE_VERSION = ET.VERSION

ETREE_VERSION = [int(i) for i in ETREE_VERSION.split(".")]

current_path = os.path.abspath(os.getcwd())

__author__     = "Francisco Amato"
__copyright__  = "Copyright (c) 2013, Infobyte LLC"
__credits__    = ["Facundo de Guzmán", "Francisco Amato"]
__license__    = ""
__version__    = "1.0.0"
__maintainer__ = "Francisco Amato"
__email__      = "famato@infobytesec.com"
__status__     = "Development"

class NiktoXmlParser(object):
    """
    The objective of this class is to parse an xml file generated by the nikto tool.

    TODO: Handle errors.
    TODO: Test nikto output version. Handle what happens if the parser doesn't support it.
    TODO: Test cases.

    @param nikto_xml_filepath A proper xml generated by nikto
    """
    def __init__(self, xml_output):
        tree = self.parse_xml(xml_output)

        if tree:
            self.hosts = [host for host in self.get_hosts(tree)]
        else:
            self.hosts = []

    def parse_xml(self, xml_output):
        """
        Open and parse an xml file.

        TODO: Write custom parser to just read the nodes that we need instead of
        reading the whole file.

        @return xml_tree An xml tree instance. None if error.
        """
        try:
            tree = ET.fromstring(xml_output)
        except SyntaxError, err:
            print "SyntaxError: %s. %s" % (err, xml_output)
            return None

        return tree

    def get_hosts(self, tree):
        """
        @return items A list of Host instances
        """
        for host_node in tree.find('niktoscan').findall('scandetails'):
            yield Host(host_node)


def get_attrib_from_subnode(xml_node, subnode_xpath_expr, attrib_name):
    """
    Finds a subnode in the item node and the retrieves a value from it

    @return An attribute value
    """
    global ETREE_VERSION
    node = None

    if ETREE_VERSION[0] <= 1 and ETREE_VERSION[1] < 3:

        match_obj = re.search("([^\@]+?)\[\@([^=]*?)=\'([^\']*?)\'",subnode_xpath_expr)
        if match_obj is not None:
            node_to_find = match_obj.group(1)
            xpath_attrib = match_obj.group(2)
            xpath_value = match_obj.group(3)
            for node_found in xml_node.findall(node_to_find):
                if node_found.attrib[xpath_attrib] == xpath_value:
                    node = node_found
                    break
        else:
            node = xml_node.find(subnode_xpath_expr)

    else:
        node = xml_node.find(subnode_xpath_expr)

    if node is not None:
        return node.get(attrib_name)

    return None


class Item(object):
    """
    An abstract representation of a Item

    TODO: Consider evaluating the attributes lazily
    TODO: Write what's expected to be present in the nodes
    TODO: Refactor both Host and the Port clases?

    @param item_node A item_node taken from an nikto xml tree
    """
    def __init__(self, item_node):
        self.node = item_node

        self.id_nikto = self.node.get('id')

        self.osvdbid = ["BID-"+self.node.get('osvdbid')] if self.node.get('osvdbid') != "0" else []
        self.osvdblink = self.node.get('osvdbidlink')
        self.method = self.node.get('method')
        self.desc = self.get_text_from_subnode('description')
        self.uri = self.get_text_from_subnode('uri')
        self.namelink = self.get_text_from_subnode('namelink')
        self.iplink = self.get_text_from_subnode('iplink')


    def get_text_from_subnode(self, subnode_xpath_expr):
        """
        Finds a subnode in the host node and the retrieves a value from it.

        @return An attribute value
        """
        sub_node = self.node.find(subnode_xpath_expr)
        if sub_node is not None:
            return sub_node.text

        return None

    def __str__(self):
        ports = []
        for port in self.ports:
            var = "    %s" % port
            ports.append(var)
        ports = "\n".join(ports)

        return "%s, %s, %s [%s], %s\n%s" % (self.hostnames, self.status,
                                           self.ipv4_address, self.mac_address, self.os, ports)

class Host(object):
    """
    An abstract representation of a Host

    @param host_node A host_node taken from an nmap xml tree
    """
    def __init__(self, host_node):
        self.node = host_node
        self.targetip = self.node.get('targetip')
        self.targethostname = self.node.get('targethostname')
        self.port = self.node.get('targetport')
        self.targetbanner = self.node.get('targetbanner')
        self.starttime = self.node.get('starttime')
        self.sitename = self.node.get('sitename')
        self.siteip = self.node.get('hostheader')
        self.items = [item for item in self.get_items()]

    def get_items(self):
        """
        @return items A list of Host instances
        """
        for item_node in self.node.findall('item'):
            yield Item(item_node)

    def __str__(self):
        ports = []
        for port in self.ports:
            var = "    %s" % port
            ports.append(var)
        ports = "\n".join(ports)

        return "%s, %s, %s [%s], %s\n%s" % (self.hostnames, self.status,
                                           self.ipv4_address, self.mac_address, self.os, ports)


class NiktoPlugin(core.PluginBase):
    """
    Example plugin to parse nikto output.
    """
    def __init__(self):
        core.PluginBase.__init__(self)
        self.id              = "Nikto"
        self.name            = "Nikto XML Output Plugin"
        self.plugin_version         = "0.0.2"
        self.version   = "2.1.5"
        self.options         = None
        self._current_output = None
        self.parent = None
        self._command_regex  = re.compile(r'^(sudo nikto|nikto|sudo nikto\.pl|nikto\.pl|perl nikto\.pl|\.\/nikto\.pl|\.\/nikto).*?')
        self._completition = {
                                "":"",
                                "-ask+":"Whether to ask about submitting updates",
                                "-Cgidirs+":'Scan these CGI dirs: "none", "all", or values like "/cgi/ /cgi-a/"',
                                "-config+":"Use this config file",
                                "-Display+":"Turn on/off display outputs:",
                                "-dbcheck":"Check database and other key files for syntax errors",
                                "-evasion+":"Encoding technique:",
                                "-Format+":"Save file (-o) format:",
                                "-Help":"Extended help information",
                                "-host+":"Target host",
                                "-IgnoreCode":"Ignore Codes--treat as negative responses",
                                "-id+":"Host authentication to use, format is id:pass or id:pass:realm",
                                "-key+":"Client certificate key file",
                                "-list-plugins":"List all available plugins, perform no testing",
                                "-maxtime+":"Maximum testing time per host",
                                "-mutate+":"Guess additional file names:",
                                "-mutate-options":"Provide information for mutates",
                                "-nointeractive":"Disables interactive features",
                                "-nolookup":"Disables DNS lookups",
                                "-nossl":"Disables the use of SSL",
                                "-no404":"Disables nikto attempting to guess a 404 page",
                                "-output+":"Write output to this file ('.' for auto-name)",
                                "-Pause+":"Pause between tests (seconds, integer or float)",
                                "-Plugins+":"List of plugins to run (default: ALL)",
                                "-port+":"Port to use (default 80)",
                                "-RSAcert+":"Client certificate file",
                                "-root+":"Prepend root value to all requests, format is /directory",
                                "-Save":"Save positive responses to this directory ('.' for auto-name)",
                                "-ssl":"Force ssl mode on port",
                                "-Tuning+":"Scan tuning:",
                                "-timeout+":"Timeout for requests (default 10 seconds)",
                                "-Userdbs":"Load only user databases, not the standard databases",
                                "-until":"Run until the specified time or duration",
                                "-update":"Update databases and plugins from CIRT.net",
                                "-useproxy":"Use the proxy defined in nikto.conf",
                                "-Version":"Print plugin and database versions",
                                "-vhost+":"Virtual host (for Host header)",
        }

        global current_path
        self._output_file_path = os.path.join(self.data_path,
                                             "nikto_output-%s.xml" % self._rid)



    def parseOutputString(self, output, debug = False ):
        """
        This method will discard the output the shell sends, it will read it from
        the xml where it expects it to be present.

        NOTE: if 'debug' is true then it is being run from a test case and the
        output being sent is valid.
        """

        parser = NiktoXmlParser(output)

        for host in parser.hosts:

            h_id = self.createAndAddHost(host.targetip)


            i_id = self.createAndAddInterface(h_id, host.targetip, ipv4_address=host.targetip,hostname_resolution=host.targethostname)
            s_id = self.createAndAddServiceToInterface(h_id, i_id, "http",
                                               "tcp",
                                               ports = [host.port],
                                               status = "open")

            n_id = self.createAndAddNoteToService(h_id,s_id,"website","")
            n2_id = self.createAndAddNoteToNote(h_id,s_id,n_id,host.targethostname,"")

            for item in host.items:
                v_id = self.createAndAddVulnWebToService(h_id, s_id,
                                                         name=item.desc, ref=item.osvdbid, website=host.targethostname,
                                                         method=item.method, path=item.namelink,query=item.uri)
        del parser

    xml_arg_re = re.compile(r"^.*(-output\s*[^\s]+).*$")

    def processCommandString(self, username, current_path, command_string):
        """
        Adds the -oX parameter to get xml output to the command string that the
        user has set.
        """
        self._output_file_path = os.path.join(self.data_path,"%s_%s_output-%s.xml" % (self.get_ws(),
                                                                                        self.id,
                                                                                        random.uniform(1,10)))
        arg_match = self.xml_arg_re.match(command_string)


        if arg_match is None:
            return re.sub(r"(^.*?nikto(\.pl)?)",
                          r"\1 -output %s -Format XML" % self._output_file_path,
                          command_string)
        else:
            data=re.sub(" \-Format XML","",command_string)
            return re.sub(arg_match.group(1),
                          r"-output %s -Format XML" % self._output_file_path,
                          data)

    def setHost(self):
        pass


def createPlugin():
    return NiktoPlugin()

if __name__ == '__main__':
    parser = NiktoXmlParser(sys.argv[1])
    for item in parser.items:
        if item.status == 'up':
            print item
