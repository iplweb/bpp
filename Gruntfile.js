const sass = require('sass');

module.exports = function (grunt) {
    grunt.initConfig({
        // pkg: grunt.file.readJSON('package.json'),

        sass: {
            options: {
                implementation: sass,
                api: 'modern-compiler',
                style: 'compressed',
		silenceDeprecations: ['global-builtin', 'import'],
                loadPaths: [
                    'node_modules/foundation-sites/scss'
                ]
            },
            blue: {
                files: {
                    'src/bpp/static/scss/app-blue.css':
                        'src/bpp/static/scss/app-blue.scss'
                }
            },
            green: {
                files: {
                    'src/bpp/static/scss/app-green.css':
                        'src/bpp/static/scss/app-green.scss'
                }
            },
            orange: {
                files: {
                    'src/bpp/static/scss/app-orange.css':
                        'src/bpp/static/scss/app-orange.scss'
                }
            }
        },

        concurrent: {
            themes: {
                tasks: ['sass:blue', 'sass:green', 'sass:orange'],
                options: {
                    logConcurrentOutput: true
                }
            }
        },

        watch: {
            grunt: {files: ['Gruntfile.js']},

            sass: {
                files: 'src/bpp/static/scss/*.scss',
                tasks: ['concurrent:themes']
            }
        },

        qunit: {
            all: ['src/notifications/static/notifications/js/tests/index.html']
        },

        shell: {
            collectstatic: {
                command: 'python src/manage.py collectstatic --noinput -v0 --traceback'
            }
        }
    });

    grunt.loadNpmTasks('grunt-sass');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.loadNpmTasks('grunt-contrib-qunit');
    grunt.loadNpmTasks('grunt-shell');
    grunt.loadNpmTasks('grunt-concurrent');

    grunt.registerTask('shell-test', ['shell:collectstatic']);
    grunt.registerTask('build', ['concurrent:themes', 'shell:collectstatic']);
    grunt.registerTask('default', ['build', 'watch']);
}
