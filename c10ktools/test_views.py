from django.core.urlresolvers import reverse

from .test import ServerTestCase


class LiveViewsTests(ServerTestCase):

    def test_basic(self):
        self.selenium.get(self.live_server_url + reverse('c10ktools.views.basic'))

        field = self.selenium.find_element_by_xpath('//form[@method="GET"]/input[@type="text"]')
        field.send_keys('spam')
        field.submit()

        result = self.selenium.find_element_by_xpath('//pre[1]')
        self.assertEqual(result.text, "<QueryDict: {'text': ['spam']}>")

        field = self.selenium.find_element_by_xpath('//form[@method="POST"]/input[@type="text"]')
        field.send_keys('eggs')
        field.submit()

        result = self.selenium.find_element_by_xpath('//pre[2]')
        self.assertEqual(result.text, "<QueryDict: {'text': ['eggs']}>")

    def test_echo(self):
        self.selenium.get(self.live_server_url + reverse('c10ktools.views.echo'))

        def get_messages():
            messages = self.selenium.find_elements_by_xpath('//ul[@id="messages"]/li')
            return [msg.text for msg in messages]

        expected_messages = [
            'Connection open.', 'Hello!',
            '1. Spam', '2. Eggs', '3. Café',
            'Goodbye!', 'Connection closed.',
        ]

        def expect_messages(count):
            self.assertEqual(get_messages(), expected_messages[:count])

        field = self.selenium.find_element_by_id('text')
        expect_messages(2)

        field.send_keys("Spam")
        field.submit()
        expect_messages(3)

        field.send_keys("Eggs")
        field.submit()
        expect_messages(4)

        field.send_keys("Café")
        field.submit()
        expect_messages(7)
