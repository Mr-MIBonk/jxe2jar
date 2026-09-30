import java.io.ByteArrayOutputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.FieldVisitor;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

/** Restore missing owners of anonymous classes using captures or constructor sites. */
public final class RepairInnerClasses {
    private static final int ASM = Opcodes.ASM9;

    private static byte[] read(InputStream input) throws IOException {
        try {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            byte[] block = new byte[8192];
            int size;
            while ((size = input.read(block)) != -1) {
                output.write(block, 0, size);
            }
            return output.toByteArray();
        } finally {
            input.close();
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            throw new IllegalArgumentException("usage: INPUT.jar OUTPUT.jar");
        }
        ZipFile source = new ZipFile(args[0]);
        List<String> entries = new ArrayList<String>();
        Enumeration<? extends ZipEntry> archiveEntries = source.entries();
        while (archiveEntries.hasMoreElements()) {
            entries.add(archiveEntries.nextElement().getName());
        }
        Set<String> names = new HashSet<String>(entries);
        final Map<String, String> restored = new HashMap<String, String>();
        final Map<String, String> staticCandidates = new HashMap<String, String>();
        final Map<String, String> nestedCandidates = new HashMap<String, String>();
        for (String entry : entries) {
            if (!entry.endsWith(".class")) {
                continue;
            }
            final String name = entry.substring(0, entry.length() - 6);
            int marker = name.lastIndexOf('$');
            if (marker < 0 || !name.substring(marker + 1).matches("[0-9]+")) {
                continue;
            }
            final String outer = name.substring(0, marker);
            if (!names.contains(outer + ".class")) {
                continue;
            }
            final boolean[] outerField = {false};
            final boolean[] incomplete = {false};
            final String[] capturedOwner = {null};
            final boolean[] ambiguousCapture = {false};
            byte[] bytes = read(source.getInputStream(source.getEntry(entry)));
            new ClassReader(bytes).accept(new ClassVisitor(ASM) {
                @Override public FieldVisitor visitField(int access, String field, String descriptor,
                                                         String signature, Object value) {
                    if (field.matches("this\\$[0-9]+")) {
                        if (descriptor.equals("L" + outer + ";")) {
                            outerField[0] = true;
                        } else if (descriptor.startsWith("L" + outer + "$")
                                && descriptor.endsWith(";")) {
                            String candidate = descriptor.substring(1, descriptor.length() - 1);
                            if (names.contains(candidate + ".class")) {
                                if (capturedOwner[0] != null && !capturedOwner[0].equals(candidate)) {
                                    ambiguousCapture[0] = true;
                                } else {
                                    capturedOwner[0] = candidate;
                                }
                            }
                        }
                    }
                    return null;
                }

                @Override public void visitInnerClass(String inner, String outerName,
                                                      String innerName, int access) {
                    if (inner.equals(name) && outerName == null && innerName == null) {
                        incomplete[0] = true;
                    }
                }
            }, ClassReader.SKIP_CODE | ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
            if (outerField[0] && incomplete[0]) {
                restored.put(name, outer);
            } else if (capturedOwner[0] != null && !ambiguousCapture[0] && incomplete[0]) {
                nestedCandidates.put(name, capturedOwner[0]);
            } else if (incomplete[0]) {
                staticCandidates.put(name, outer);
            }
        }

        // Static anonymous classes have no this$ capture. A flattened class
        // such as Foo$2 can instead capture Foo$1. For either case require a
        // NEW in the proposed lexical owner before restoring its metadata.
        Map<String, Set<String>> byOuter = new HashMap<String, Set<String>>();
        Map<String, String> candidates = new HashMap<String, String>(staticCandidates);
        candidates.putAll(nestedCandidates);
        for (Map.Entry<String, String> candidate : candidates.entrySet()) {
            Set<String> children = byOuter.get(candidate.getValue());
            if (children == null) {
                children = new HashSet<String>();
                byOuter.put(candidate.getValue(), children);
            }
            children.add(candidate.getKey());
        }
        for (final Map.Entry<String, Set<String>> group : byOuter.entrySet()) {
            byte[] bytes = read(source.getInputStream(source.getEntry(group.getKey() + ".class")));
            new ClassReader(bytes).accept(new ClassVisitor(ASM) {
                @Override public MethodVisitor visitMethod(int access, String method,
                                                           String descriptor, String signature,
                                                           String[] exceptions) {
                    return new MethodVisitor(ASM) {
                        @Override public void visitTypeInsn(int opcode, String type) {
                            if (opcode == Opcodes.NEW && group.getValue().contains(type)) {
                                restored.put(type, group.getKey());
                            }
                        }
                    };
                }
            }, ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
        }

        int changedClasses = 0;
        ZipOutputStream output = new ZipOutputStream(new FileOutputStream(args[1]));
        for (String entry : entries) {
            byte[] bytes = read(source.getInputStream(source.getEntry(entry)));
            if (entry.endsWith(".class")) {
                final boolean[] changed = {false};
                ClassReader reader = new ClassReader(bytes);
                ClassWriter writer = new ClassWriter(reader, 0);
                reader.accept(new ClassVisitor(ASM, writer) {
                    @Override public void visitInnerClass(String inner, String outerName,
                                                          String innerName, int access) {
                        String owner = restored.get(inner);
                        if (owner != null && outerName == null && innerName == null) {
                            outerName = owner;
                            changed[0] = true;
                        }
                        super.visitInnerClass(inner, outerName, innerName, access);
                    }
                }, 0);
                if (changed[0]) {
                    bytes = writer.toByteArray();
                    changedClasses++;
                }
            }
            output.putNextEntry(new ZipEntry(entry));
            output.write(bytes);
            output.closeEntry();
        }
        output.close();
        source.close();
        List<String> sorted = new ArrayList<String>(restored.keySet());
        Collections.sort(sorted);
        System.out.println("restored anonymous classes: " + sorted.size()
            + "; classfiles with repaired InnerClasses entries: " + changedClasses);
        for (String inner : sorted) {
            System.out.println(inner + " -> " + restored.get(inner));
        }
    }
}
