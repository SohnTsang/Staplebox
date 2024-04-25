from django.core.management.base import BaseCommand
from companies.models import CompanyProfile
from folder.models import Folder

class Command(BaseCommand):
    help = 'Creates folders for existing company profiles without one'

    def handle(self, *args, **options):
        for company in CompanyProfile.objects.filter(partners_contract_folder__isnull=True):
            folder = Folder.objects.create(name=f"{company.name} Contracts", description="Storage for partners' contracts.")
            company.partners_contract_folder = folder
            company.save()
            self.stdout.write(self.style.SUCCESS(f'Folder created for {company.name}'))
