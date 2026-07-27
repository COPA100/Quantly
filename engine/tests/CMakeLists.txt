include(FetchContent)

FetchContent_Declare(
  Catch2
  GIT_REPOSITORY https://github.com/catchorg/Catch2.git
  GIT_TAG v3.7.1
)
FetchContent_MakeAvailable(Catch2)

add_executable(quantly_tests
  test_drawdown.cpp
  test_correlation.cpp
  test_var.cpp
)
target_link_libraries(quantly_tests PRIVATE quantly_core Catch2::Catch2WithMain)

if(MINGW)
  # static runtime so the test binary runs without the ucrt64 dlls on PATH
  target_link_options(quantly_tests PRIVATE -static -static-libgcc -static-libstdc++)
endif()

list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
include(Catch)
catch_discover_tests(quantly_tests)
