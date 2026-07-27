cmake_minimum_required(VERSION 3.15)
project(quantly_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_engine
  src/cpp/module.cpp
  src/cpp/drawdown.cpp
)
target_include_directories(_engine PRIVATE src/cpp)

if(MINGW)
  # link the mingw runtime statically so the .pyd loads under a stock
  # (msvc-built) cpython without the ucrt64 dlls needing to be on PATH
  target_link_options(_engine PRIVATE -static -static-libgcc -static-libstdc++)
endif()

install(TARGETS _engine DESTINATION engine)
