from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import StudentModel
from .models import TasksDifficultyModel
from .models import TaskInstanceModel
from .models import StudentTaskInfoModel
from .models import PracticeSession
from .models import SessionTaskInstance


class StudentResource(resources.ModelResource):
    class Meta:
        model = StudentModel


class TasksDifficultyResource(resources.ModelResource):
    class Meta:
        model = TasksDifficultyModel


class TaskInstanceResource(resources.ModelResource):
    class Meta:
        model = TaskInstanceModel


@admin.register(StudentModel)
class StudentsSkillAdmin(ImportExportModelAdmin):
    resource_class = StudentResource

@admin.register(TasksDifficultyModel)
class TasksDifficultyAdmin(ImportExportModelAdmin):
    resource_class = TasksDifficultyResource

@admin.register(TaskInstanceModel)
class TaskInstanceAdmin(ImportExportModelAdmin):
    resource_class = TaskInstanceResource


# other models registration
admin.site.register(StudentTaskInfoModel)
admin.site.register(PracticeSession)
admin.site.register(SessionTaskInstance)
