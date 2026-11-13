set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

add_sources_from_current_dir(utils
  nemo_shell.c
  utils/agent_mutex_name.c
  utils/agent_named_pipe_name.c
  utils/arm_arch_queries.c
  utils/aux_match_opt.c
  utils/blink_time.c
  utils/centre_window.c
  utils/cmdline_arg.c
  utils/cryptoapi.c
  utils/defaults.c
  utils/dll_hijacking_protection.c
  utils/dputs.c
  utils/escape_registry_key.c
  utils/filename.c
  utils/fontspec.c
  utils/getdlgitemtext_alloc.c
  utils/get_system_dir.c
  utils/get_username.c
  utils/gui-timing.c
  utils/interprocess_mutex.c
  utils/is_console_handle.c
  utils/load_system32_dll.c
  utils/ltime.c
  utils/makedlgitemborderless.c
  utils/make_spr_sw_abort_winerror.c
  utils/message_box.c
  utils/minefield.c
  utils/open_for_write_would_lose_data.c
  utils/pgp_fingerprints_msgbox.c
  utils/platform_get_x_display.c
  utils/registry.c
  utils/request_file.c
  utils/screenshot.c
  utils/security.c
  utils/shinydialogbox.c
  utils/split_into_argv.c
  utils/split_into_argv_w.c
  utils/subprocess_waiter.c
  utils/version.c
  utils/win_strerror.c
  unicode.c)
if(NOT HAVE_STRTOUMAX)
  add_sources_from_current_dir(utils utils/strtoumax.c)
endif()
add_sources_from_current_dir(eventloop
  cliloop.c handle-wait.c)
add_sources_from_current_dir(console
  select-cli.c nohelp.c console.c)
add_sources_from_current_dir(settings
  storage.c)
add_sources_from_current_dir(network
  network.c handle-socket.c named-pipe-client.c named-pipe-server.c local-proxy.c x11.c)
add_sources_from_current_dir(sshcommon
  noise.c)
add_sources_from_current_dir(sshclient
  agent-client.c gss.c sharing.c)
add_sources_from_current_dir(sftpclient
  sftp.c)
add_sources_from_current_dir(otherbackends
  serial.c)
add_sources_from_current_dir(agent
  agent-client.c)
add_sources_from_current_dir(guiterminal
  nemo_debug.c
  nemo_tabs_layout.c
  nemo_gl.c nemo_d2d.c nemo_d2d_api.cpp nemo_gpu.c
  nemo_font_cmap.c nemo_font_fallback.c
  nemo_cluster.cpp
  nemo_link_ui.c nemo_clipboard.c nemo_key_input.c nemo_osc52_ui.c
  dialog.c controls.c config.c printing.c jump-list.c sizetip.c nemo_snapshot.c)
target_link_libraries(guiterminal cabinet)
add_executable(test_cluster_renderer
  ${CMAKE_SOURCE_DIR}/../../tests/test_cluster_renderer.cpp nemo_cluster.cpp)
target_link_libraries(test_cluster_renderer ${platform_libraries})
add_executable(test_gl_lifetime ${CMAKE_SOURCE_DIR}/../../tests/test_gl_lifetime.c)
target_link_libraries(test_gl_lifetime utils ${platform_libraries})
# The COM bridges do not throw or use RTTI. Keep the portable frontend free
# of a compiler-specific C++ runtime DLL as well as the static MSVC build.
foreach(cluster_target guiterminal test_cluster_renderer)
  if(MSVC)
    target_compile_options(${cluster_target} PRIVATE $<$<COMPILE_LANGUAGE:CXX>:/GR->)
  else()
    target_compile_options(${cluster_target} PRIVATE
      $<$<COMPILE_LANGUAGE:CXX>:-fno-rtti> $<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions>)
  endif()
endforeach()
add_dependencies(guiterminal generated_licence_h) # dialog.c uses licence.h

# This object awkwardly needs to live in the network library as well
# as the eventloop library, in case it didn't get pulled in from the
# latter before handle-socket.c needed it.
add_library(handle-io OBJECT
  handle-io.c)
target_sources(eventloop PRIVATE $<TARGET_OBJECTS:handle-io>)
target_sources(network PRIVATE $<TARGET_OBJECTS:handle-io>)

add_library(guimisc STATIC
  select-gui.c)

add_executable(pageant
  pageant.c
  help.c
  pageant.rc)
add_dependencies(pageant generated_licence_h)
target_link_libraries(pageant
  guimisc eventloop agent network crypto utils
  ${platform_libraries})
set_target_properties(pageant PROPERTIES WIN32_EXECUTABLE ON)
installed_program(pageant)

add_sources_from_current_dir(plink no-jump-list.c nohelp.c plink.rc)
add_dependencies(plink generated_licence_h)

add_sources_from_current_dir(pscp no-jump-list.c nohelp.c pscp.rc)
add_dependencies(pscp generated_licence_h)

add_sources_from_current_dir(psftp no-jump-list.c nohelp.c psftp.rc)
add_dependencies(psftp generated_licence_h)

add_sources_from_current_dir(psocks nohelp.c)

add_executable(putty
  window.c
  putty.c
  help.c
  ${CMAKE_SOURCE_DIR}/stubs/no-console.c
  putty.rc)
be_list(putty PuTTY SSH SERIAL OTHERBACKENDS)
add_dependencies(putty generated_licence_h)
target_link_libraries(putty
  guiterminal guimisc eventloop sshclient otherbackends settings network crypto
  utils
  ${platform_libraries})
set_target_properties(putty PROPERTIES WIN32_EXECUTABLE ON)
installed_program(putty)

add_executable(puttytel
  window.c
  putty.c
  help.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-ca-config.c
  ${CMAKE_SOURCE_DIR}/stubs/no-console.c
  ${CMAKE_SOURCE_DIR}/stubs/no-rand.c
  ${CMAKE_SOURCE_DIR}/stubs/no-dit.c
  ${CMAKE_SOURCE_DIR}/proxy/nocproxy.c
  ${CMAKE_SOURCE_DIR}/proxy/nosshproxy.c
  puttytel.rc)
be_list(puttytel PuTTYtel SERIAL OTHERBACKENDS)
add_dependencies(puttytel generated_licence_h)
target_link_libraries(puttytel
  guiterminal guimisc eventloop otherbackends settings network utils
  ${platform_libraries})
set_target_properties(puttytel PROPERTIES WIN32_EXECUTABLE ON)
installed_program(puttytel)

add_executable(puttygen
  puttygen.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  noise.c
  no-jump-list.c
  storage.c
  help.c
  ${CMAKE_SOURCE_DIR}/sshpubk.c
  ${CMAKE_SOURCE_DIR}/sshrand.c
  controls.c
  puttygen.rc)
add_dependencies(puttygen generated_licence_h)
target_link_libraries(puttygen
  keygen guimisc crypto utils
  ${platform_libraries})
set_target_properties(puttygen PROPERTIES WIN32_EXECUTABLE ON)
installed_program(puttygen)

if(HAVE_CONPTY)
  option(NEMOTERM_SINGLE_EXE "Link frontend into the OpenConsole host executable" OFF)
  if(NEMOTERM_SINGLE_EXE)
    add_library(pterm STATIC)
    target_compile_definitions(pterm PRIVATE NEMOTERM_SINGLE_EXE WinMain=NemoGuiMain)
  else()
    add_executable(pterm)
    target_sources(pterm PRIVATE pterm.rc)
  endif()
  target_sources(pterm PRIVATE
    window.c
    pterm.c
    help.c
    conpty.c
    ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
    ${CMAKE_SOURCE_DIR}/stubs/no-ca-config.c
    ${CMAKE_SOURCE_DIR}/stubs/no-console.c
    ${CMAKE_SOURCE_DIR}/stubs/no-rand.c
    ${CMAKE_SOURCE_DIR}/stubs/no-dit.c
    ${CMAKE_SOURCE_DIR}/proxy/nosshproxy.c)
  be_list(pterm Nemoterm)
  add_dependencies(pterm generated_licence_h)
  target_link_libraries(pterm
    guiterminal guimisc eventloop settings network utils
    ${platform_libraries})
  set_target_properties(pterm PROPERTIES WIN32_EXECUTABLE ON OUTPUT_NAME nemoterm)
  if(NOT NEMOTERM_SINGLE_EXE)
    installed_program(pterm)
  endif()
else()
  message("ConPTY not available; cannot build Windows pterm")
endif()

add_executable(test_split_into_argv
  test/test_split_into_argv.c)
target_compile_definitions(test_split_into_argv PRIVATE TEST)
target_link_libraries(test_split_into_argv utils ${platform_libraries})

add_executable(test_screenshot
  test/test_screenshot.c)
target_link_libraries(test_screenshot utils ${platform_libraries})

add_executable(test_lineedit
  ${CMAKE_SOURCE_DIR}/test/test_lineedit.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-logging.c
  ${CMAKE_SOURCE_DIR}/stubs/no-printing.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_lineedit
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_terminal
  ${CMAKE_SOURCE_DIR}/test/test_terminal.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_terminal
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_sixel_terminal
  ${CMAKE_SOURCE_DIR}/test/test_sixel_terminal.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_sixel_terminal
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_resize
  ${CMAKE_SOURCE_DIR}/test/test_resize.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_resize
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_mouse
  ${CMAKE_SOURCE_DIR}/test/test_mouse.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_mouse
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_modes
  ${CMAKE_SOURCE_DIR}/test/test_modes.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_modes
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_sgr
  ${CMAKE_SOURCE_DIR}/test/test_sgr.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_sgr
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_queries
  ${CMAKE_SOURCE_DIR}/test/test_queries.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_queries
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_titles
  ${CMAKE_SOURCE_DIR}/test/test_titles.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_titles
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_tcap
  ${CMAKE_SOURCE_DIR}/test/test_tcap.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_tcap
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_hyperlink
  ${CMAKE_SOURCE_DIR}/test/test_hyperlink.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  no-jump-list.c)
target_link_libraries(test_hyperlink
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_keyboard
  ${CMAKE_SOURCE_DIR}/test/test_keyboard.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_keyboard
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_mok
  ${CMAKE_SOURCE_DIR}/test/test_mok.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_mok
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_win32_input
  ${CMAKE_SOURCE_DIR}/test/test_win32_input.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_win32_input
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_state_control
  ${CMAKE_SOURCE_DIR}/test/test_state_control.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_state_control
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_selective_erase
  ${CMAKE_SOURCE_DIR}/test/test_selective_erase.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_selective_erase
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_rectangle
  ${CMAKE_SOURCE_DIR}/test/test_rectangle.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_rectangle
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_margins
  ${CMAKE_SOURCE_DIR}/test/test_margins.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_margins
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_shell_marks
  ${CMAKE_SOURCE_DIR}/test/test_shell_marks.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_shell_marks
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_grapheme_terminal
  ${CMAKE_SOURCE_DIR}/test/test_grapheme_terminal.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_grapheme_terminal
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_cwd
  ${CMAKE_SOURCE_DIR}/test/test_cwd.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_cwd
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_reflow
  ${CMAKE_SOURCE_DIR}/test/test_reflow.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_reflow
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_osc52
  ${CMAKE_SOURCE_DIR}/test/test_osc52.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_osc52
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_highlight
  ${CMAKE_SOURCE_DIR}/test/test_highlight.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  no-jump-list.c)
target_link_libraries(test_highlight
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_sync
  ${CMAKE_SOURCE_DIR}/test/test_sync.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  no-jump-list.c)
target_link_libraries(test_sync
  guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_osc_colour
  ${CMAKE_SOURCE_DIR}/test/test_osc_colour.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  no-jump-list.c)
target_link_libraries(test_osc_colour
  guiterminal settings eventloop utils ${platform_libraries})

add_sources_from_current_dir(test_conf no-jump-list.c handle-wait.c)

add_executable(test_snapshot ${CMAKE_SOURCE_DIR}/../../tests/test_snapshot.c nemo_snapshot.c)
target_link_libraries(test_snapshot cabinet gdi32 user32)

add_executable(test_shell test/test_shell.c
  ${CMAKE_SOURCE_DIR}/stubs/no-gss.c
  ${CMAKE_SOURCE_DIR}/stubs/no-storage.c
  ${CMAKE_SOURCE_DIR}/stubs/no-timing.c
  no-jump-list.c)
target_link_libraries(test_shell guiterminal settings eventloop utils ${platform_libraries})

add_executable(test_font_cmap ${CMAKE_SOURCE_DIR}/../../tests/test_font_cmap.c nemo_font_cmap.c)
target_include_directories(test_font_cmap PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
add_executable(test_tabs_layout ${CMAKE_SOURCE_DIR}/../../tests/test_tabs_layout.c nemo_tabs_layout.c)
target_include_directories(test_tabs_layout PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
add_executable(test_font_fallback test/test_font_fallback.c test/test_font_fallback.rc)
target_include_directories(test_font_fallback PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(test_font_fallback guiterminal utils ${platform_libraries})
