/**
 * Communication with server Task API.
 * @ngInject
 */
angular.module('flocs.services')
.factory('taskDao', function ($http) {

  // public API
  return {
    gettingAllTaskIds: gettingAllTaskIds,
    gettingTaskById: gettingTaskById,
    gettingTaskByIdWithToolbox: gettingTaskByIdWithToolbox,
  };

  // private implementation

  /**
   * Return promise of getting list of ids of all tasks.
   */
  function gettingAllTaskIds() {
    return $http.get('/api/tasks/get-ids')
      .then(function(response) {
        return response.data.ids;
      });
  }

  /**
   * Return promise of getting task by given id.
   */
  function gettingTaskById(id) {
    return $http.get('/api/tasks/get-task/' + id)
      .then(function(response) {
        return response.data;
      });
  }

  /**
   * Return promise of getting task by given id.
   */
  function gettingTaskByIdWithToolbox(id) {
    return $http.get('/api/tasks/get-task-and-toolbox/' + id)
      .then(function(response) {
        return response.data;
      });
  }


});
