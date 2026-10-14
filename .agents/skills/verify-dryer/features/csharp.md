# C#

dryer reads `.cs` files as C#, and compares methods and the other members that have a body. A user sees this as which C# spans a pair names, how two C# members score, and which C# files a run leaves out as test code.

## Sub-features

- `csharp-pair` two C# methods that differ only in local names, the members they read, and literal values pair at `1.00`, with `:language "csharp"`; an unrelated method beside them pairs with neither.
- `csharp-callee` a different called method, conditional-access member, generic method, constructed type, or call inside an object initializer scores below `1.00`.
- `csharp-members` methods, constructors, destructors, operators, conversion operators, accessors with a body, and `=>` properties and indexers are compared. Bodiless members, local functions, and lambdas are not.
- `csharp-test-projects` a `.cs` file in a C# test project, or in a C# project's `bin/` or `obj/`, is left out of a directory walk and `--changed`, and compared when named. A file's project is the nearest folder holding a `.csproj`, and only that folder's name counts.

## How to get to it (user POV)

- Run `./dryer src` in a C# project, and read which spans the pairs name.
- To see every member dryer compares, run `./dryer --threshold 0 --min-lines 1 --min-nodes 1 <file>`. Every compared member then pairs with every other one.

## Driving it with verify-dryer

Preconditions:

- `$vd doctor` prints `doctor: ok`.
- `project=$($vd project empty)` for each recipe. `T` is the transcript path for the feature.

**csharp-pair.** Put these three files, then run `$vd drive "$project" "$T" src`.

```bash
$vd put "$project" src/Left.cs <<'EOF'
class Left
{
    int Alpha(int[] xs)
    {
        var total = xs.Length + 1;
        var label = "a" + $"left {Total(xs)}";
        Log(label);
        return Count(total, label);
    }
}
EOF
$vd put "$project" src/Right.cs <<'EOF'
class Right
{
    int Beta(int[] items)
    {
        var sum = items.Count + 2.5;
        var name = @"b" + $"right {Total(items)}";
        Log(name);
        return Count(sum, name);
    }
}
EOF
$vd put "$project" src/Other.cs <<'EOF'
class Other
{
    void Gamma(string path)
    {
        if (File.Exists(path))
        {
            File.Delete(path);
        }
        Console.WriteLine(path);
    }
}
EOF
```

Pass: exit `0`; stdout is one `DUPLICATE score=1.00` block, `src/Left.cs:3-9` with `src/Right.cs:3-9`, and nothing names `src/Other.cs`. The transcript's `.metrics/dry.edn` holds that one candidate with `:language "csharp"`.

**csharp-callee.** Each pair is one returned expression. Put each side in a class of its own, then score the two files:

```bash
n=0
while IFS='|' read -r left right; do
  n=$((n + 1))
  printf 'class A\n{\n    object M(object x, object xs, object odd, object items, object even)\n    {\n        return %s;\n    }\n}\n' "$left" | $vd put "$project" "src/A$n.cs"
  printf 'class B\n{\n    object M(object x, object xs, object odd, object items, object even)\n    {\n        return %s;\n    }\n}\n' "$right" | $vd put "$project" "src/B$n.cs"
  $vd drive "$project" "$T" --edn --threshold 0 --min-lines 1 --min-nodes 1 "src/A$n.cs" "src/B$n.cs"
done <<'EOF'
xs.Filter(odd)|items.Filter(even)
xs.Filter(odd)|xs.Select(odd)
Console.WriteLine(x)|Console.Write(x)
this.Foo(x)|this.Bar(x)
x?.Foo()|x?.Bar()
Gen<int>(x)|Other<int>(x)
Outer.Gen<int>(x)|Outer.Other<int>(x)
new List<int>()|new HashSet<int>()
new System.Text.StringBuilder()|new System.IO.StringWriter()
new Foo { A = 1 }|new Bar { A = 1 }
new Foo(x) { A = Compute(x) }|new Foo(x) { A = Other(x) }
EOF
```

Pass: each drive exits `0` with one candidate. The first, the control with renamed locals, has `:score 1.0`. Every other one has `:score` below `1.0`.

**csharp-members.** Put this file, then run `$vd drive "$project" "$T" --threshold 0 --min-lines 1 --min-nodes 1 src/Board.cs`.

```bash
$vd put "$project" src/Board.cs <<'EOF'
namespace Demo;

public abstract class Board
{
    public Board(int start)
    {
        total = start;
    }
    ~Board()
    {
        Dispose();
    }
    public abstract void Declared();
    public partial void Later();
    public int Alpha(int[] xs)
    {
        int Local(int q) { return q + 1; }
        Func<int, int> f = x => { return x * 2; };
        return Local(xs.Length) + f(1);
    }
    public int Beta() => total + 1;
    public int Auto { get; set; }
    public int Count => total;
    public int Kept
    {
        get { return total; }
        set { total = value; }
    }
    public int this[int i] => items[i];
    public static Board operator +(Board a, Board b) { return a; }
    public static implicit operator int(Board b) => b.total;
    public event EventHandler Changed
    {
        add { handlers += value; }
        remove { handlers -= value; }
    }
}

public interface IShape
{
    double Area();
    double Twice() { return Area() * 2; }
}

public record Point(int X, int Y)
{
    public int Sum() { return X + Y; }
}

public struct Cell
{
    public int Value() { return 1; }
}
EOF
```

Pass: exit `0`; the spans start on exactly these 15 lines: 5 (constructor), 9 (destructor), 15 (`Alpha`), 21 (`Beta`), 23 (`Count`), 26 (`get`), 27 (`set`), 29 (indexer), 30 (operator), 31 (conversion operator), 34 (`add`), 35 (`remove`), 42 (`Twice`), 47 (`Sum`), and 52 (`Value`). That is 105 `DUPLICATE` blocks. No span starts on line 13 (abstract), 14 (bodiless partial), 17 (local function), 18 (lambda), 22 (auto-property), or 41 (bodiless interface method).

**csharp-test-projects.** Put one method in fifteen places, fourteen project files, and two Python files:

```bash
calc='class Calc
{
    int Sum(int[] xs)
    {
        var total = 0;
        foreach (var x in xs) { total += x; }
        return Scale(total, 2);
    }
}'
for dir in src/App src/App/obj/Debug/net10.0 src/Lib Runner.MicrosoftTestPlatform App.Tests App.UnitTests App.Test App.Test.Unit App.UnitTest tests Checks Probe Harness Meta; do
  printf '%s\n' "$calc" | $vd put "$project" "$dir/Calc.cs"
done
printf '%s\n' "$calc" | $vd put "$project" Prod/Tests/Helper.cs
for proj in src/App/App Prod/Prod App.Tests/App.Tests App.UnitTests/App.UnitTests App.Test/App.Test App.Test.Unit/App.Test.Unit; do
  printf '<Project Sdk="Microsoft.NET.Sdk" />\n' | $vd put "$project" "$proj.csproj"
done
printf '<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n    <TargetFramework>net10.0</TargetFramework>\n  </PropertyGroup>\n</Project>\n' | $vd put "$project" src/Lib/Lib.csproj
printf '<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n    <IsTestProject>true</IsTestProject>\n  </PropertyGroup>\n</Project>\n' | $vd put "$project" Checks/Checks.csproj
printf '<Project Sdk="Microsoft.NET.Sdk">\n  <ItemGroup>\n    <PackageReference Include="NUnit" Version="4.2.2" />\n  </ItemGroup>\n</Project>\n' | $vd put "$project" Probe/Probe.csproj
printf '<Project Sdk="Microsoft.NET.Sdk">\n  <ItemGroup>\n    <PackageReference Include="Microsoft.Testing.Platform" />\n  </ItemGroup>\n</Project>\n' | $vd put "$project" Runner.MicrosoftTestPlatform/Runner.MicrosoftTestPlatform.csproj
printf '<Project Sdk="MSTest.Sdk/4.2.2">\n  <ItemGroup>\n    <PackageReference Include="Moq" />\n  </ItemGroup>\n</Project>\n' | $vd put "$project" Harness/Harness.csproj
printf '<Project Sdk="Microsoft.NET.Sdk">\n  <ItemGroup>\n    <PackageReference Include="Microsoft.NET.Test.Sdk" />\n  </ItemGroup>\n</Project>\n' | $vd put "$project" App.UnitTest/App.UnitTest.csproj
printf '<Project Sdk="Microsoft.NET.Sdk">\n  <ItemGroup>\n    <PackageReference Include="MSTest" />\n  </ItemGroup>\n</Project>\n' | $vd put "$project" Meta/Meta.csproj
printf 'def a(xs):\n    return f(xs) + 1\n' | $vd put "$project" App.Tests/a.py
printf 'def b(ys):\n    return f(ys) + 2\n' | $vd put "$project" App.Tests/b.py
```

Then drive these four, with the files left untracked:

1. `$vd drive "$project" "$T" --threshold 0 --min-lines 1 --min-nodes 1`. Pass: exit `0`; seven `DUPLICATE` blocks. Six pair `src/App/Calc.cs`, `src/Lib/Calc.cs`, `Prod/Tests/Helper.cs` and `Runner.MicrosoftTestPlatform/Calc.cs` with one another, and one names `App.Tests/a.py` and `App.Tests/b.py`. No block names another file, `src/App/obj/Debug/net10.0/Calc.cs` included.
2. `$vd drive "$project" "$T" --changed --threshold 0 --min-lines 1 --min-nodes 1`. Pass: the same seven blocks.
3. `$vd drive "$project" "$T" --threshold 0 --min-lines 1 --min-nodes 1 App.Tests/Calc.cs src/App/Calc.cs`. Pass: one block, naming both files.
4. `$vd drive "$project" "$T" --help`. Pass: the help says C# files in a test project, and in a C# project's `bin/` and `obj/`, are skipped, and names the folder signs and the `.csproj` signs.

## Gotchas

- A file's project is the nearest folder at or above it that holds a `.csproj`, and a file with none is in no test project. The project is a test project by its own folder's name, not a folder inside or above it, so `Prod/Tests/Helper.cs` in a plain `Prod` project is compared. Its `.csproj` can mark it too: `<IsTestProject>true</IsTestProject>`, the `MSTest.Sdk` project SDK, or a PackageReference to Microsoft.NET.Test.Sdk, NUnit, xunit, xunit.v3, MSTest, or MSTest.TestFramework. A folder name that ends in `Test`, such as `App.UnitTest`, isn't a sign by itself: Stryker's production `Stryker.TestRunner.VsTest` ends that way. A reference to Microsoft.Testing.Platform marks nothing, since a test runner such as Stryker's uses it as a library. The rule reads only `.cs` files, so the Python files under `App.Tests/` are compared, as they are today.
- `--changed` counts untracked files: it runs `git status --untracked-files=all`.
- The text report shows two members that share a line range with the same `file:start-end`, so the members recipe puts each accessor on its own line.
