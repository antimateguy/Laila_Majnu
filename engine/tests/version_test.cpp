#include <catch2/catch_test_macros.hpp>

#include <cstddef>
#include <string_view>

#include "lm/core/version.hpp"

namespace {

// Mirrors the semver pattern in schemas/common.schema.json, which the API enforces on engine_version.
bool is_semver(std::string_view v) {
  int dots = 0;
  bool digit_seen = false;
  for (std::size_t i = 0; i < v.size(); ++i) {
    const char c = v[i];
    if (c == '.') {
      if (!digit_seen) return false;
      ++dots;
      digit_seen = false;
    } else if (c >= '0' && c <= '9') {
      if (c == '0' && !digit_seen && i + 1 < v.size() && v[i + 1] != '.') return false;  // no leading zeros
      digit_seen = true;
    } else {
      return false;
    }
  }
  return dots == 2 && digit_seen;
}

}  // namespace

TEST_CASE("engine version comes from the CMake project version") {
  CHECK(lm::kEngineVersion == "0.1.0");
}

TEST_CASE("engine version satisfies the payload's semver contract") {
  CHECK(is_semver(lm::kEngineVersion));
  CHECK_FALSE(is_semver("1.0"));
  CHECK_FALSE(is_semver("01.0.0"));
  CHECK_FALSE(is_semver("1.0.0-rc1"));
}
