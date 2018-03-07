module.exports = function (grunt) {
    grunt.initConfig({
        // pkg: grunt.file.readJSON('package.json'),

        sass: {
            options: {
                includePaths: [
		    'node_modules/foundation-sites/scss'
		]
            },
            dist: {
                options: {
                    outputStyle: 'compressed',
		    loadPath: ['node_modules/foundation-sites/scss'],
                },
                files: {
                    'src/bpp/static/scss/app-blue.css':
                        'src/bpp/static/scss/app-blue.scss',

                    'src/bpp/static/scss/app-green.css':
                        'src/bpp/static/scss/app-green.scss'
                }
            }
        },

        watch: {
            grunt: {files: ['Gruntfile.js']},

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

    grunt.registerTask('build', ['sass',]);
    grunt.registerTask('default', ['build', 'watch']);
}
