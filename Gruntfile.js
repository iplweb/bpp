const sass = require('sass');

module.exports = function (grunt) {
    grunt.initConfig({
        // pkg: grunt.file.readJSON('package.json'),

        sass: {
            options: {
                implementation: sass,
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
                        'src/bpp/static/scss/app-green.scss',
                    'src/bpp/static/scss/app-orange.css':
                        'src/bpp/static/scss/app-orange.scss'

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
        },

        shell: {
            collectstatic: {
                command: 'python src/manage.py collectstatic --noinput -v0'
            }
        }
    });

    grunt.loadNpmTasks('grunt-sass');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.loadNpmTasks('grunt-contrib-qunit');
    grunt.loadNpmTasks('grunt-shell');

    grunt.registerTask('build', ['sass', 'shell:collectstatic']);
    grunt.registerTask('default', ['build', 'watch']);
}
