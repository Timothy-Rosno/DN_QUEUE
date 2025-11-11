from django.core.management.base import BaseCommand
from calendarEditor.models import Machine


class Command(BaseCommand):
    help = 'Populate the database with initial machine data'

    def handle(self, *args, **options):
        # Delete existing machines if any
        Machine.objects.all().delete()

        # Create Hidalgo
        hidalgo = Machine.objects.create(
            name='Hidalgo',
            min_temp=0.01,
            max_temp=300,
            b_field_x=1,
            b_field_y=1,
            b_field_z=6,
            b_field_direction='parallel_perpendicular',
            dc_lines=48,
            rf_lines=32,
            daughterboard_type='QBoard II',
            optical_capabilities='none',
            cooldown_hours=36,
            current_status='idle',
            is_available=True,
            description='Advanced cryogenic system with versatile B-field capabilities',
            location='NANO 325'
        )
        self.stdout.write(self.style.SUCCESS(f'Created machine: {hidalgo.name}'))

        # Create Griffin
        griffin = Machine.objects.create(
            name='Griffin',
            min_temp=0.01,
            max_temp=300,
            b_field_x=0,
            b_field_y=0,
            b_field_z=12,
            b_field_direction='parallel_perpendicular',
            dc_lines=48,
            rf_lines=32,
            daughterboard_type='QBoard I or QBoard II',
            optical_capabilities='with_work',
            cooldown_hours=36,
            current_status='idle',
            is_available=True,
            description='High-field cryogenic system with optical capabilities (requires setup)',
            location='NANO 324'
        )
        self.stdout.write(self.style.SUCCESS(f'Created machine: {griffin.name}'))

        # Create Kiutra
        kiutra = Machine.objects.create(
            name='Kiutra',
            min_temp=0.1,
            max_temp=220,
            b_field_x=0,
            b_field_y=0,
            b_field_z=5,
            b_field_direction='parallel_perpendicular',
            dc_lines=48,
            rf_lines=6,
            daughterboard_type='QBoard II',
            optical_capabilities='none',
            cooldown_hours=36,
            current_status='idle',
            is_available=True,
            description='Compact cryogenic refrigerator with moderate B-field',
            location='NANO 324'
        )
        self.stdout.write(self.style.SUCCESS(f'Created machine: {kiutra.name}'))

        # Create Opticool
        opticool = Machine.objects.create(
            name='Opticool',
            min_temp=2,
            max_temp=350,
            b_field_x=0,
            b_field_y=0,
            b_field_z=7,
            b_field_direction='perpendicular',
            dc_lines=16,
            rf_lines=6,
            daughterboard_type='QBoard I',
            optical_capabilities='under_construction',
            cooldown_hours=36,
            current_status='idle',
            is_available=True,
            description='Optical cryostat with perpendicular B-field and optical capabilities',
            location='NANO 325'
        )
        self.stdout.write(self.style.SUCCESS(f'Created machine: {opticool.name}'))

        # Create CryoCore
        cryocore = Machine.objects.create(
            name='CryoCore',
            min_temp=4,
            max_temp=350,
            b_field_x=0,
            b_field_y=0,
            b_field_z=0,
            b_field_direction='none',
            dc_lines=12,
            rf_lines=2,
            daughterboard_type='Montana Puck',
            optical_capabilities='under_construction',
            cooldown_hours=36,
            current_status='idle',
            is_available=True,
            description='Basic cryogenic system (note: RF lines currently broken)',
            location='NANO 324'
        )
        self.stdout.write(self.style.SUCCESS(f'Created machine: {cryocore.name}'))

        self.stdout.write(self.style.SUCCESS('\nSuccessfully populated all machines!'))
        self.stdout.write('\nMachine Summary:')
        self.stdout.write(f'  - {hidalgo.name}: {hidalgo.min_temp}K-{hidalgo.max_temp}K, B-field: {hidalgo.b_field_z}T (Z), {hidalgo.get_b_field_direction_display()}, {hidalgo.dc_lines} DC/{hidalgo.rf_lines} RF, {hidalgo.daughterboard_type}, {hidalgo.location}')
        self.stdout.write(f'  - {griffin.name}: {griffin.min_temp}K-{griffin.max_temp}K, B-field: {griffin.b_field_z}T (Z), {griffin.get_b_field_direction_display()}, {griffin.dc_lines} DC/{griffin.rf_lines} RF, {griffin.daughterboard_type}, {griffin.location}')
        self.stdout.write(f'  - {kiutra.name}: {kiutra.min_temp}K-{kiutra.max_temp}K, B-field: {kiutra.b_field_z}T (Z), {kiutra.get_b_field_direction_display()}, {kiutra.dc_lines} DC/{kiutra.rf_lines} RF, {kiutra.daughterboard_type}, {kiutra.location}')
        self.stdout.write(f'  - {opticool.name}: {opticool.min_temp}K-{opticool.max_temp}K, B-field: {opticool.b_field_z}T (Z), {opticool.get_b_field_direction_display()}, {opticool.dc_lines} DC/{opticool.rf_lines} RF, {opticool.daughterboard_type}, {opticool.location}')
        self.stdout.write(f'  - {cryocore.name}: {cryocore.min_temp}K-{cryocore.max_temp}K, No B-field, {cryocore.dc_lines} DC/{cryocore.rf_lines} RF, {cryocore.daughterboard_type}, {cryocore.location}')
