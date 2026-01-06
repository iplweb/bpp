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
            },
            adminthemes: {
                files: {
                    'src/bpp/static/bpp/css/admin-themes.css':
                        'src/bpp/static/bpp/scss/admin-themes.scss'
                }
            },
            adminfilterpanel: {
                files: {
                    'src/bpp/static/bpp/css/admin-filter-panel.css':
                        'src/bpp/static/bpp/scss/admin-filter-panel.scss'
                }
            },
            przemapuj_zrodla: {
                files: {
                    'src/przemapuj_zrodla_pbn/static/przemapuj_zrodla_pbn/css/przemapuj-zrodla.css':
                        'src/przemapuj_zrodla_pbn/static/przemapuj_zrodla_pbn/scss/przemapuj-zrodla.scss'
                }
            },
            deduplikator_autorow: {
                files: {
                    'src/deduplikator_autorow/static/deduplikator_autorow/css/deduplikator_autorow.css':
                        'src/deduplikator_autorow/static/deduplikator_autorow/scss/deduplikator_autorow.scss'
                }
            },
            deduplikator_zrodel: {
                files: {
                    'src/deduplikator_zrodel/static/deduplikator_zrodel/css/deduplikator_zrodel.css':
                        'src/deduplikator_zrodel/static/deduplikator_zrodel/scss/deduplikator_zrodel.scss'
                }
            },
            ewaluacja_optymalizuj_publikacje: {
                files: {
                    'src/ewaluacja_optymalizuj_publikacje/static/ewaluacja_optymalizuj_publikacje/css/ewaluacja_optymalizuj_publikacje.css':
                        'src/ewaluacja_optymalizuj_publikacje/static/ewaluacja_optymalizuj_publikacje/scss/ewaluacja_optymalizuj_publikacje.scss'
                }
            },
            pbn_downloader_app: {
                files: {
                    'src/pbn_downloader_app/static/pbn_downloader_app/css/pbn_downloader_app.css':
                        'src/pbn_downloader_app/static/pbn_downloader_app/scss/pbn_downloader_app.scss'
                }
            },
            pbn_export_queue: {
                files: {
                    'src/pbn_export_queue/static/pbn_export_queue/css/pbn_export_queue.css':
                        'src/pbn_export_queue/static/pbn_export_queue/scss/pbn_export_queue.scss'
                }
            },
            przemapuj_prace_autora: {
                files: {
                    'src/przemapuj_prace_autora/static/przemapuj_prace_autora/css/admin.css':
                        'src/przemapuj_prace_autora/static/przemapuj_prace_autora/scss/admin.scss'
                }
            },
            ewaluacja_liczba_n: {
                files: {
                    'src/ewaluacja_liczba_n/static/ewaluacja_liczba_n/css/ewaluacja_liczba_n.css':
                        'src/ewaluacja_liczba_n/static/ewaluacja_liczba_n/scss/ewaluacja_liczba_n.scss'
                }
            },
            ewaluacja_dwudyscyplinowcy: {
                files: {
                    'src/ewaluacja_dwudyscyplinowcy/static/ewaluacja_dwudyscyplinowcy/css/ewaluacja_dwudyscyplinowcy.css':
                        'src/ewaluacja_dwudyscyplinowcy/static/ewaluacja_dwudyscyplinowcy/scss/ewaluacja_dwudyscyplinowcy.scss'
                }
            },
            pbn_import: {
                files: {
                    'src/pbn_import/static/pbn_import/css/pbn_import.css':
                        'src/pbn_import/static/pbn_import/scss/pbn_import.scss'
                }
            },
            pbn_komparator_zrodel: {
                files: {
                    'src/pbn_komparator_zrodel/static/pbn_komparator_zrodel/css/pbn_komparator_zrodel.css':
                        'src/pbn_komparator_zrodel/static/pbn_komparator_zrodel/scss/pbn_komparator_zrodel.scss'
                }
            },
            bpp_setup_wizard: {
                files: {
                    'src/bpp_setup_wizard/static/bpp_setup_wizard/css/bpp_setup_wizard.css':
                        'src/bpp_setup_wizard/static/bpp_setup_wizard/scss/bpp_setup_wizard.scss'
                }
            },
            komparator_publikacji_pbn: {
                files: {
                    'src/komparator_publikacji_pbn/static/komparator_publikacji_pbn/css/komparator_publikacji_pbn.css':
                        'src/komparator_publikacji_pbn/static/komparator_publikacji_pbn/scss/komparator_publikacji_pbn.scss'
                }
            }
        },

        concurrent: {
            themes: {
                tasks: [
                    'sass:blue',
                    'sass:green',
                    'sass:orange',
                    'sass:adminthemes',
                    'sass:adminfilterpanel',
                    'sass:przemapuj_zrodla',
                    'sass:deduplikator_autorow',
                    'sass:deduplikator_zrodel',
                    'sass:ewaluacja_optymalizuj_publikacje',
                    'sass:pbn_downloader_app',
                    'sass:pbn_export_queue',
                    'sass:przemapuj_prace_autora',
                    'sass:ewaluacja_liczba_n',
                    'sass:ewaluacja_dwudyscyplinowcy',
                    'sass:pbn_import',
                    'sass:pbn_komparator_zrodel',
                    'sass:bpp_setup_wizard',
                    'sass:komparator_publikacji_pbn'
                ],
                options: {
                    logConcurrentOutput: true
                }
            }
        },

        "_watch": {
            grunt: {files: ['Gruntfile.js']},

            sass: {
                files: ['src/bpp/static/scss/*.scss','src/bpp/static/bpp/scss/*.scss'],
                tasks: ['concurrent:themes']
            }

        },

        qunit: {
            all: ['src/notifications/static/notifications/js/tests/index.html']
        },

        shell: {
            esbuild: {
                command: 'npx esbuild src/bpp/static/bpp/js/bundle-entry.js ' +
                         '--bundle --minify-syntax --minify-whitespace --sourcemap ' +
                         '--outfile=src/bpp/static/bpp/js/dist/bundle.js ' +
                         '--format=iife --target=es2018 ' +
                         '--inject:src/bpp/static/bpp/js/jquery-shim.js ' +
                         '--define:global=window'
            },
            // Post-process bundle to fix IIFE scope issues
            // django-autocomplete-light: yl namespace (esbuild renames to yl2)
            patchBundle: {
                command: "sed -i.bak 's/var yl2=yl2||{}/window.yl=window.yl||{};var yl2=window.yl/g' " +
                    "src/bpp/static/bpp/js/dist/bundle.js && " +
                    "rm -f src/bpp/static/bpp/js/dist/bundle.js.bak"
            },
            collectstatic: {
                command: 'uv run src/manage.py collectstatic --noinput -v0 --traceback'
            }
        }
    });

    grunt.loadNpmTasks('grunt-sass');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.loadNpmTasks('grunt-contrib-qunit');
    grunt.loadNpmTasks('grunt-shell');
    grunt.loadNpmTasks('grunt-concurrent');

    grunt.registerTask('shell-test', ['shell:collectstatic']);
    grunt.registerTask('build', [
        'concurrent:themes',
        'shell:esbuild',
        'shell:patchBundle',
        'shell:collectstatic'
    ]);
    grunt.registerTask('build-non-interactive', [
        'concurrent:themes',
        'shell:esbuild',
        'shell:patchBundle'
    ]);

    // Rename the original watch task and create an alias that builds first
    grunt.renameTask('watch', '_watch');
    grunt.registerTask('watch', ['build', '_watch']);
    grunt.registerTask('default', ['watch']);
}
