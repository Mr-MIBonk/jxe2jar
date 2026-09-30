import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.io.StringWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

/** One fresh javac task per source; the file manager and process are reused. */
public final class IsolatedCompileRunner {
    public static void main(String[] args) throws Exception {
        if (args.length != 4) {
            throw new IllegalArgumentException("usage: JCL-or-- CLASSPATH EMPTY_SOURCEPATH OUTPUT_DIR");
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            throw new IllegalStateException("run with a JDK, not a JRE");
        }
        StandardJavaFileManager files = compiler.getStandardFileManager(null, Locale.ROOT, null);
        BufferedReader input = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
        String row;
        while ((row = input.readLine()) != null) {
            int separator = row.indexOf('\t');
            int second = row.indexOf('\t', separator + 1);
            if (separator < 0 || second < 0) {
                throw new IllegalArgumentException("expected SOURCE<TAB>TARGET<TAB>PATH: " + row);
            }
            String level = row.substring(0, separator);
            String target = row.substring(separator + 1, second);
            String path = row.substring(second + 1);
            List<String> options = new ArrayList<String>();
            options.add("-nowarn");
            options.add("-proc:none");
            options.add("-Xmaxerrs");
            options.add("20");
            options.add("-source");
            options.add(level);
            options.add("-target");
            options.add(target);
            if (level.equals("1.4") && !args[0].equals("-")) {
                options.add("-bootclasspath");
                options.add(args[0]);
            }
            options.add("-cp");
            options.add(args[1]);
            options.add("-sourcepath");
            options.add(args[2]);
            options.add("-d");
            options.add(args[3]);

            DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<JavaFileObject>();
            boolean passed = false;
            String error = "";
            try {
                JavaCompiler.CompilationTask task = compiler.getTask(new StringWriter(), files,
                    diagnostics, options, null, files.getJavaFileObjects(new File(path)));
                passed = task.call().booleanValue();
                for (Diagnostic<? extends JavaFileObject> diagnostic : diagnostics.getDiagnostics()) {
                    if (diagnostic.getKind() == Diagnostic.Kind.ERROR) {
                        error = diagnostic.getLineNumber() + ":" + diagnostic.getColumnNumber()
                            + ":" + diagnostic.getStartPosition() + ":" + diagnostic.getEndPosition()
                            + ": " + diagnostic.getMessage(Locale.ROOT);
                        break;
                    }
                }
            } catch (RuntimeException failure) {
                error = failure.toString();
            }
            System.out.println((passed ? "OK" : "FAIL") + "\t" + path + "\t"
                + error.replace('\t', ' ').replace('\n', ' ').replace('\r', ' '));
        }
        files.close();
    }
}
