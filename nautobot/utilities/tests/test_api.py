from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status

from nautobot.dcim import models as dcim_models
from nautobot.extras import choices
from nautobot.extras import models as extras_models
from nautobot.ipam import models as ipam_models
from nautobot.utilities import testing


class WritableNestedSerializerTest(testing.APITestCase):
    """
    Test the operation of WritableNestedSerializer using VLANSerializer as our test subject.
    """

    def setUp(self):
        super().setUp()

        self.region_a = dcim_models.Region.objects.filter(sites__isnull=True).first()
        self.site1 = dcim_models.Site.objects.create(region=self.region_a, name="Site 1", slug="site-1")
        self.site2 = dcim_models.Site.objects.create(region=self.region_a, name="Site 2", slug="site-2")

    def test_related_by_pk(self):
        data = {
            "vid": 100,
            "name": "Test VLAN 100",
            "site": self.site1.pk,
            "status": "active",
        }
        url = reverse("ipam-api:vlan-list")
        self.add_permissions("ipam.add_vlan")

        response = self.client.post(url, data, format="json", **self.header)
        self.assertHttpStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(response.data["site"]["id"], str(self.site1.pk))
        vlan = ipam_models.VLAN.objects.get(pk=response.data["id"])
        self.assertEqual(vlan.site, self.site1)

    def test_related_by_pk_no_match(self):
        data = {
            "vid": 100,
            "name": "Test VLAN 100",
            "site": "00000000-0000-0000-0000-0000000009eb",
            "status": "active",
        }
        url = reverse("ipam-api:vlan-list")
        self.add_permissions("ipam.add_vlan")

        with testing.disable_warnings("django.request"):
            response = self.client.post(url, data, format="json", **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ipam_models.VLAN.objects.filter(name="Test VLAN 100").count(), 0)
        self.assertTrue(response.data["site"][0].startswith("Related object not found"))

    def test_related_by_attributes(self):
        data = {
            "vid": 100,
            "name": "Test VLAN 100",
            "status": "active",
            "site": {"name": "Site 1"},
        }
        url = reverse("ipam-api:vlan-list")
        self.add_permissions("ipam.add_vlan")

        response = self.client.post(url, data, format="json", **self.header)
        self.assertHttpStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(response.data["site"]["id"], str(self.site1.pk))
        vlan = ipam_models.VLAN.objects.get(pk=response.data["id"])
        self.assertEqual(vlan.site, self.site1)

    def test_related_by_attributes_no_match(self):
        data = {
            "vid": 100,
            "name": "Test VLAN 100",
            "status": "active",
            "site": {"name": "Site X"},
        }
        url = reverse("ipam-api:vlan-list")
        self.add_permissions("ipam.add_vlan")

        with testing.disable_warnings("django.request"):
            response = self.client.post(url, data, format="json", **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ipam_models.VLAN.objects.filter(name="Test VLAN 100").count(), 0)
        self.assertTrue(response.data["site"][0].startswith("Related object not found"))

    def test_related_by_attributes_multiple_matches(self):
        data = {
            "vid": 100,
            "name": "Test VLAN 100",
            "status": "active",
            "site": {
                "region": {
                    "name": self.region_a.name,
                },
            },
        }
        url = reverse("ipam-api:vlan-list")
        self.add_permissions("ipam.add_vlan")

        with testing.disable_warnings("django.request"):
            response = self.client.post(url, data, format="json", **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ipam_models.VLAN.objects.filter(name="Test VLAN 100").count(), 0)
        self.assertTrue(response.data["site"][0].startswith("Multiple objects match"))

    def test_related_by_invalid(self):
        data = {
            "vid": 100,
            "name": "Test VLAN 100",
            "site": "XXX",
            "status": "active",
        }
        url = reverse("ipam-api:vlan-list")
        self.add_permissions("ipam.add_vlan")

        with testing.disable_warnings("django.request"):
            response = self.client.post(url, data, format="json", **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ipam_models.VLAN.objects.filter(name="Test VLAN 100").count(), 0)


class APIDocsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Populate a CustomField to activate CustomFieldSerializer
        content_type = ContentType.objects.get_for_model(dcim_models.Site)
        self.cf_text = extras_models.CustomField(type=choices.CustomFieldTypeChoices.TYPE_TEXT, name="test")
        self.cf_text.save()
        self.cf_text.content_types.set([content_type])
        self.cf_text.save()

    def test_api_docs(self):
        url = reverse("api_docs")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        headers = {
            "HTTP_ACCEPT": "application/vnd.oai.openapi",
        }
        url = reverse("schema")
        response = self.client.get(url, **headers)
        self.assertEqual(response.status_code, 200)
