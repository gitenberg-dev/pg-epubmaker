from lxml import etree

root = etree.fromstring ("""
<html xml:lang="en" lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <body>
     <p>
       <span style="color: red"></span>black
     </p>
  </body>
</html>
""")

XHTML11_DOCTYPE = "<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.1//EN' \
'http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd'>"

print (etree.tostring (
        root,
        method = 'xml',
        xml_declaration = True,
        doctype = XHTML11_DOCTYPE,
        encoding = 'utf-8', 
        pretty_print = True))
