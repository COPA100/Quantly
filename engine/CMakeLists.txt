cmake_minimum_required(VERSION 3.15)
project(quantly_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(QUANTLY_BUILD_TESTS "Build the C++ unit tests instead of the python module" OFF)

# pure-c++ compute, shared by the python module and the c++ unit tests. no
# pybind/python dependency, so the tests build with a bare toolchain.
add_library(quantly_core STATIC
  src/cpp/drawdown.cpp
  src/cpp/correlation.cpp
  src/cpp/var.cpp
)
target_include_directories(quantly_core PUBLIC src/cpp)
set_target_properties(quantly_core PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(QUANTLY_BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests)
else()
  find_package(pybind11 CONFIG REQUIRED)
  pybind11_add_module(_engine src/cpp/module.cpp)
  target_link_libraries(_engine PRIVATE quantly_core)
  if(MINGW)
    # link the mingw runtime statically so the .pyd loads under a stock
    # (msvc-built) cpython without the ucrt64 dlls needing to be on PATH
    target_link_options(_engine PRIVATE -static -static-libgcc -static-libstdc++)
  endif()
  install(TARGETS _engine DESTINATION engine)
endif()
