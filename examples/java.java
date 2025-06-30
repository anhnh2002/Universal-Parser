import java.util.List;
import java.util.ArrayList;
import java.util.HashMap;
import java.io.*;
import static java.lang.Math.PI;
import static java.lang.System.out;

public class ImportExample {
    public static void main(String[] args) {
        // Using ArrayList and List
        List<String> names = new ArrayList<>();
        names.add("Alice");
        names.add("Bob");
        
        // Using HashMap
        HashMap<String, Integer> ages = new HashMap<>();
        ages.put("Alice", 25);
        ages.put("Bob", 30);
        
        // Using static import for Math.PI
        double circumference = 2 * PI * 5.0;
        
        // Using static import for System.out
        out.println("Names: " + names);
        out.println("Ages: " + ages);
        out.println("Circumference: " + circumference);
        
        // Using java.io for file operations
        try {
            File file = new File("example.txt");
            FileWriter writer = new FileWriter(file);
            writer.write("Hello World!");
            writer.close();
            
            BufferedReader reader = new BufferedReader(new FileReader(file));
            String content = reader.readLine();
            out.println("File content: " + content);
            reader.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}