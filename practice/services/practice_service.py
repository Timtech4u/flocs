"""
Main service functions of practice app.
"""

import logging

from common.flow_factors import FlowFactors
from tasks.models import TaskModel
from practice.models.practice_context import create_practice_context
from practice.models import TaskInstanceModel
from practice.models import StudentTaskInfoModel
from practice.models import StudentModel
from practice.models.task_instance import FlowRating
from practice.services.parameters_update import update_parameters
from practice.services.instructions_service import get_instructions
from practice.services import practice_session_service
from practice.core.credits import difficulty_to_credits
from practice.core.flow_prediction import predict_flow
from practice.core.task_selection import ScoreTaskSelector, IdSpecifidedTaskSelector

logger = logging.getLogger(__name__)


def get_task_by_id(student, task_id):
    return get_task(student, IdSpecifidedTaskSelector(task_id))


def get_next_task(student):
    return get_task(student, ScoreTaskSelector())


def get_task(student, task_selector):
    """
    Return next task for given student. Also create a new task instance record
    in DB and update student-task info for selected task (namely the reference
    to last task instance).

    Returns:
        dictionary with information about assigned task

    Raises:
        ValueError: If the student argument is None.
        LookupError: If there is no task available.
    """
    logger.info("Getting next task for student id %s", student.id)
    if not student:
        raise ValueError('Student is required for get_next_task')

    practice_context = create_practice_context(user=student)
    task_ids = practice_context.get_all_task_ids()
    if not task_ids:
        raise LookupError('No tasks available.')

    # set next task in session
    student_model = StudentModel.objects.get(user_id=student.pk)
    practice_session_service.next_task_in_session(student_model)

    task_id = task_selector.select(task_ids, student.id, practice_context)
    predicted_flow = predict_flow(student.id, task_id, practice_context)
    task = TaskModel.objects.get(pk=task_id)
    task_instance = TaskInstanceModel.objects.create(student=student,
            task=task, predicted_flow=predicted_flow, session=student_model.session)
    student_task_info = StudentTaskInfoModel.objects.get_or_create(
            student=student, task=task)[0]
    student_task_info.last_instance = task_instance
    student_task_info.save()

    instructions = get_instructions(student, task)

    task_dictionary = task.to_json()
    task_instance_dictionary = {
        'task-instance-id': task_instance.pk,
        'task': task_dictionary,
        'task_in_session' : student_model.session.task_counter,
        'instructions': instructions
    }
    logger.info("Task %s successfully picked for student %s", task_id, student.id)
    return task_instance_dictionary


def process_attempt_report(student, report):
    """Process reported result of a solution attempt of a task

    Args:
        student: user who took the attempt
        report: dictionary with the fields specified in:
            https://github.com/effa/flocs/wiki/Server-API#apipracticeattempt-report

    Returns:
        - whether the task is solved for the first time
        - number of earned-credits

    Raises:
        ValueError:
            - If the student argument is None.
            - If the report doesn't belong to the student.
            - If it's reporting an obsolete attempt (i.e. new attempt was
              already processed).
    """
    if not student:
        raise ValueError('Student is required for process_task_result')

    task_instance_id = report['task-instance-id']
    attempt_count = report['attempt']
    solved = report['solved']
    given_up = report['given-up']
    time = report['time']

    logger.info("Reporting attempt for student %s with result %s", student.id, solved)

    task_instance = TaskInstanceModel.objects.get(id=task_instance_id)
    if  attempt_count < task_instance.attempt_count:
        # It means that this report is obsolete. Note that we allow for
        # equality of attempts count, which means that we want to update the
        # last report with more information (e.g. added flow report).
        raise ValueError("Obsolete attempt report can't be processed.")

    if student.id != task_instance.student.id:
        raise ValueError("Report doesn't belong to the student.")

    task_instance.update_after_attempt(
            attempt_count=attempt_count,
            time=time,
            solved=solved,
    )
    task_instance.save()
    task = task_instance.task
    student_task_info = StudentTaskInfoModel.objects.get_or_create(student=student, task=task)[0]
    solved_before = student_task_info.last_solved_instance is not None
    student_task_info.update(task_instance)

    credits = 0
    if solved:
        task = task_instance.task
        practice_context = create_practice_context(user=student, task=task)
        practice_context.update('solution-count', task=task.id, update=lambda n: n + 1)
        practice_context.save()
        if not solved_before:
            task_difficulty = practice_context.get(FlowFactors.TASK_BIAS, task=task.id)
            credits = difficulty_to_credits(task_difficulty)
    task_solved_first_time = solved and not solved_before,
    logger.info("Reporting attempt was successful for student %s with result %s", student.id, solved)
    return (task_solved_first_time, credits)


def process_flow_report(student, task_instance_id, given_up=False, reported_flow=None):
    """Process reported flow after the task completion (or giving up)
    """
    if given_up:
        reported_flow = FlowRating.VERY_DIFFICULT
    if not reported_flow:
        return
    task_instance = TaskInstanceModel.objects.get(id=task_instance_id)
    if student.id != task_instance.student.id:
        raise ValueError("The task instance doesn't belong to this student.")
    task_instance.set_reported_flow(reported_flow)
    task_instance.save()
    task = task_instance.task
    practice_context = create_practice_context(user=student, task=task)
    update_parameters(practice_context, student.id, task.id,
            task_instance.get_reported_flow(),
            task_instance.get_predicted_flow())
    # NOTE: There is a race condition when 2 students are updating parameters
    # for the same task at the same time. In the current conditons, this is
    # rare and if it happens it does not cause any problems (one update is
    # ignored). But if it changes in the future (many users using the system at
    # the same time), then we might want to eliminate the race condition.
    # Possible solution is probably to use select_for_update, but then it's
    # necessary to make sure that there is as little blocking as possible
    # (assigning update functions to the practice_context then
    # select_for_update current parameters, update them at once ("in parallel")
    # and save.
    practice_context.save()
