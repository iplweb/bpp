

module.exports = function(grunt) {
  grunt.initConfig({
	  // pkg: grunt.file.readJSON('package.json'),

    sass: {
      options: {
        includePaths: ['src/components/bower_components/foundation/scss']
      },
      dist: {
        options: {
          outputStyle: 'compressed'
        },
        files: {
          'src/bpp/static/scss/app.css': 'src/bpp/static/scss/app.scss'
        }
      }
    },

    watch: {
      grunt: { files: ['Gruntfile.js'] },

      sass: {
        files: 'src/bpp/static/scss/*.scss',
        tasks: ['sass']
      }
    },

    qunit: {
      all: ['src/notifications/static/notifications/js/tests/index.html']
    }
  });

  grunt.loadNpmTasks('grunt-sass');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-contrib-qunit');

  grunt.registerTask('build', ['sass']);
  grunt.registerTask('default', ['build','watch']);
}