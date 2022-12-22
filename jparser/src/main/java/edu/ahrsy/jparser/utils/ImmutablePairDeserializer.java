package edu.ahrsy.jparser.utils;

import com.google.gson.*;
import org.apache.commons.lang3.tuple.ImmutablePair;

import java.lang.reflect.Type;

public class ImmutablePairDeserializer implements JsonDeserializer<ImmutablePair<String, String>> {
  @Override
  public ImmutablePair<String, String> deserialize(JsonElement jsonElement,
          Type type,
          JsonDeserializationContext jsonDeserializationContext) throws JsonParseException {
    var array = jsonElement.getAsJsonArray();
    return new ImmutablePair<>(array.get(0).getAsString(), array.get(1).getAsString());
  }
}
