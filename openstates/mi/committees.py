import re

import lxml.html
from pupa.scrape import Scraper, Organization


class MICommitteeScraper(Scraper):
    def scrape(self, chamber=None):
        if chamber == 'lower':
            yield from self.scrape_house_committees()
        elif chamber == 'upper':
            yield from self.scrape_senate_committees()
        else:
            yield from self.scrape_house_committees()
            yield from self.scrape_senate_committees()

    def scrape_house_committees(self):
        base_url = 'http://house.mi.gov/MHRPublic/CommitteeInfo.aspx?comkey='
        html = self.get('http://house.mi.gov/mhrpublic/committee.aspx').text
        doc = lxml.html.fromstring(html)

        # get values out of drop down
        for opt in doc.xpath('//option'):
            name = opt.text
            # skip invalid choice
            if opt.text in ('Statutory Committees', 'Select One'):
                continue
            if 'have not been created' in opt.text:
                self.warning('no committees yet for the house')
                return
            com_url = base_url + opt.get('value')
            com_html = self.get(com_url).text
            cdoc = lxml.html.fromstring(com_html)
            com = Organization(chamber='lower', name=name, classification='committee')
            com.add_source(com_url)

            for a in doc.xpath('//a[starts-with(@id, "memberLink")]'):
                name = a.text.strip()

            # all links to http:// pages in servicecolumn2 are legislators
            members = cdoc.xpath('//div[contains(@id,"memberPanelRow")]')
            for mem in members:
                name = mem.xpath('./a')
                if name:
                    name = name[0].text.strip()
                else:
                    # this is a blank row
                    continue
                text = mem.xpath('./span')[0].text
                if 'Committee Chair' in text:
                    role = 'chair'
                elif 'Vice-Chair' in text:
                    role = 'vice chair'
                else:
                    role = 'member'
                com.add_member(name, role=role)

            yield com

    def scrape_senate_committees(self):
        url = 'http://www.senate.michigan.gov/committee.html'
        html = self.get(url).text
        doc = lxml.html.fromstring(html)
        doc.make_links_absolute(url)

        for link in doc.xpath('//li/a[contains(@href, "/committee/")]/@href'):
            if link.endswith('appropssubcommittee.html'):
                yield from self.scrape_approp_subcommittees(link)
            elif not link.endswith(('statutory.htm', 'pdf', 'taskforce.html')):
                yield from self.scrape_senate_committee(link)

    def scrape_senate_committee(self, url):
        html = self.get(url).text
        doc = lxml.html.fromstring(html)

        name = doc.xpath('//div[@id="committeeleft"]//h2[1]/text()')[0]
        name = name.replace(' Committee', '')

        com = Organization(chamber='upper', name=name, classification='committee')

        for member in doc.xpath('//div[@id="committeeright"]//a'):
            member_name = member.text.strip()

            # don't add clerks
            if member_name == 'Committee Clerk':
                continue

            # skip phone links
            if member.get("href").startswith("tel:"):
                continue

            if 'Committee Chair' in member.tail:
                role = 'chair'
            elif 'Majority Vice' in member.tail:
                role = 'majority vice chair'
            elif 'Minority Vice' in member.tail:
                role = 'minority vice chair'
            else:
                role = 'member'

            com.add_member(member_name, role=role)

        com.add_source(url)
        yield com

    def scrape_approp_subcommittees(self, url):
        html = self.get(url).text
        doc = lxml.html.fromstring(html)

        for strong in doc.xpath('//strong'):
            com = Organization(
                name=strong.text.strip(),
                parent_id={
                    'name': 'Appropriations',
                    'classification': 'committee',
                },
                classification='committee',
            )
            com.add_source(url)

            legislators = strong.getnext().tail.replace('Senators', '').strip()
            for leg in re.split(', | and ', legislators):
                if leg.endswith('(C)'):
                    role = 'chairman'
                    leg = leg[:-4]
                elif leg.endswith('(VC)'):
                    role = 'vice chairman'
                    leg = leg[:-5]
                elif leg.endswith('(MVC)'):
                    role = 'minority vice chairman'
                    leg = leg[:-6]
                else:
                    role = 'member'
                com.add_member(leg, role=role)

            yield com
