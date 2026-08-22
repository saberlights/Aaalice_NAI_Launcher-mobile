import '../../lib/data/models/version/version_info.dart';

void main() {
  final cases = <({String newer, String current, bool expected})>[
    (
      newer: '1.0.0-beta11-v5.8',
      current: '1.0.0-beta11+15',
      expected: true,
    ),
    (
      newer: 'v1.0.0-beta11-v5.10',
      current: '1.0.0-beta11-v5.10+16',
      expected: false,
    ),
    (
      newer: '1.0.0-beta11-v5.9',
      current: '1.0.0-beta11-v5.10+16',
      expected: false,
    ),
  ];

  for (final testCase in cases) {
    final actual = VersionInfoComparator.isNewer(
      testCase.newer,
      testCase.current,
    );
    if (actual != testCase.expected) {
      throw StateError(
        'Version comparison failed: ${testCase.newer} vs '
        '${testCase.current}; expected ${testCase.expected}, got $actual',
      );
    }
  }
}
